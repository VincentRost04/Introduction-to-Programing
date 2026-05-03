"""
build_fred.py — ETL script: Retrieves FRED CPI time series and builds a DuckDB database.

Run this script ONCE to create `data/fred.db`. The database is committed to the
repository, so subsequent runs are only needed if you want to refresh the data.

Usage
-----
    uv run python data/build_fred.py

Requires a FRED_API_KEY in your `.env` file. Request one at:
    https://fred.stlouisfed.org/docs/api/api_key.html
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred


# Be a good API citizen: small delay between calls + retries with backoff
FRED_REQUEST_DELAY_S = 0.8
FRED_MAX_RETRIES = 4


# ---------------------------------------------------------------------------
# Configuration: series to retrieve
# ---------------------------------------------------------------------------
# Seven CPI sub-indices and one monetary-policy series.
# Source: U.S. Bureau of Labor Statistics & Federal Reserve Board, via FRED.
SERIES_CONFIG: list[dict[str, str]] = [
    # CPI — seven consumption categories (index, 1982–84 = 100)
    {"id": "CPIAUCSL", "category": "total",          "name": "All Items (Headline CPI)",       "variable_type": "cpi"},
    {"id": "CPILFESL", "category": "core",           "name": "All Items Less Food and Energy", "variable_type": "cpi"},
    {"id": "CPIFABSL", "category": "food",           "name": "Food and Beverages",             "variable_type": "cpi"},
    {"id": "CPIHOSSL", "category": "housing",        "name": "Housing",                        "variable_type": "cpi"},
    {"id": "CPITRNSL", "category": "transportation", "name": "Transportation",                 "variable_type": "cpi"},
    {"id": "CPIMEDSL", "category": "medical",        "name": "Medical Care",                   "variable_type": "cpi"},
    {"id": "CPIENGSL", "category": "energy",         "name": "Energy",                         "variable_type": "cpi"},
    # Monetary policy — the Fed's main policy instrument (percent, monthly average)
    {"id": "FEDFUNDS", "category": "policy_rate",    "name": "Effective Federal Funds Rate",   "variable_type": "policy"},
]

START_DATE = "1990-01-01"
DB_PATH = Path(__file__).parent / "fred.db"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_api_key() -> str:
    """Load FRED_API_KEY from the `.env` file or exit with a helpful message."""
    load_dotenv()
    key = os.getenv("FRED_API_KEY")
    if not key or key == "your_32_character_api_key_here":
        sys.exit(
            "\nERROR: FRED_API_KEY not found or still set to the placeholder.\n"
            "  1. Request a free key at https://fred.stlouisfed.org/docs/api/api_key.html\n"
            "  2. Copy `.env.example` to `.env` in the project root\n"
            "  3. Paste your key as FRED_API_KEY=<your_key>\n"
        )
    return key


def _call_with_retries(fn, *args, label: str = "", **kwargs):
    """Call a FRED API function with retry + exponential backoff for transient errors."""
    last_exc: Exception | None = None
    for attempt in range(1, FRED_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # fredapi raises ValueError for HTTP errors
            last_exc = exc
            # Transient HTTP errors (500 etc.) wait and retry; bail otherwise
            if "Internal Server Error" in str(exc) or "Too Many Requests" in str(exc):
                wait = 1.5 * (2 ** (attempt - 1))
                print(f"\n    [retry {attempt}/{FRED_MAX_RETRIES}] {label}: "
                      f"{exc} — waiting {wait:.1f}s", end="")
                time.sleep(wait)
                continue
            raise
    # Exhausted retries
    assert last_exc is not None
    raise last_exc


def fetch_series(fred: Fred, series_id: str, start: str) -> pd.DataFrame:
    """Fetch one FRED series; return a DataFrame with columns (date, value)."""
    series = _call_with_retries(
        fred.get_series,
        series_id,
        observation_start=start,
        label=f"get_series({series_id})",
    )
    df = series.reset_index()
    df.columns = ["date", "value"]
    df = df.dropna()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


# ---------------------------------------------------------------------------
# Main ETL logic
# ---------------------------------------------------------------------------
def build_database(fred: Fred) -> None:
    """Create an empty DuckDB database and populate it with series + observations."""
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing database: {DB_PATH}")

    con = duckdb.connect(str(DB_PATH))

    # Schema
    con.execute("""
        CREATE TABLE series (
            series_id     VARCHAR PRIMARY KEY,
            category      VARCHAR NOT NULL UNIQUE,
            name          VARCHAR NOT NULL,
            unit          VARCHAR NOT NULL,
            frequency     VARCHAR NOT NULL,
            seasonal_adj  BOOLEAN NOT NULL,
            variable_type VARCHAR NOT NULL,
            source        VARCHAR NOT NULL,
            fred_url      VARCHAR NOT NULL
        );
    """)

    con.execute("""
        CREATE TABLE observations (
            series_id VARCHAR NOT NULL,
            date      DATE    NOT NULL,
            value     DOUBLE  NOT NULL,
            PRIMARY KEY (series_id, date),
            FOREIGN KEY (series_id) REFERENCES series(series_id)
        );
    """)

    print(f"Created empty database at {DB_PATH}")
    print(f"Retrieving {len(SERIES_CONFIG)} series from FRED (since {START_DATE})...\n")

    for i, cfg in enumerate(SERIES_CONFIG):
        series_id = cfg["id"]
        print(f"  {series_id:10s}  {cfg['category']:15s} ... ", end="", flush=True)

        info = _call_with_retries(
            fred.get_series_info, series_id,
            label=f"get_series_info({series_id})",
        )
        time.sleep(FRED_REQUEST_DELAY_S)
        obs = fetch_series(fred, series_id, START_DATE)
        if i < len(SERIES_CONFIG) - 1:
            time.sleep(FRED_REQUEST_DELAY_S)

        # Different sources for CPI vs policy series
        source = (
            "Federal Reserve Board (Board of Governors)"
            if cfg["variable_type"] == "policy"
            else "U.S. Bureau of Labor Statistics"
        )

        # series-level metadata
        con.execute(
            """
            INSERT INTO series
                (series_id, category, name, unit, frequency, seasonal_adj,
                 variable_type, source, fred_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                series_id,
                cfg["category"],
                cfg["name"],
                info.get("units_short", info.get("units", "Index 1982-1984=100")),
                info.get("frequency_short", info.get("frequency", "M")),
                info.get("seasonal_adjustment_short", "SA") in ("SA", "Seasonally Adjusted"),
                cfg["variable_type"],
                source,
                f"https://fred.stlouisfed.org/series/{series_id}",
            ],
        )

        # observations (bulk insert via pandas DataFrame)
        obs_with_id = obs.copy()
        obs_with_id.insert(0, "series_id", series_id)
        con.register("obs_df", obs_with_id)
        con.execute("INSERT INTO observations SELECT * FROM obs_df")
        con.unregister("obs_df")

        print(f"{len(obs):>5d} obs  [{obs['date'].min()} → {obs['date'].max()}]")

    # Verification
    n_series = con.execute("SELECT COUNT(*) FROM series").fetchone()[0]
    n_obs = con.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    date_range = con.execute(
        "SELECT MIN(date), MAX(date) FROM observations"
    ).fetchone()

    con.close()

    print("\n" + "-" * 60)
    print("Database built successfully!")
    print(f"  Path:         {DB_PATH}")
    print(f"  Series:       {n_series}")
    print(f"  Observations: {n_obs:,}")
    print(f"  Date range:   {date_range[0]} → {date_range[1]}")
    print("-" * 60)
    print("You can now remove this script from your workflow — the database")
    print("is committed to the repo and is the single source of truth.")


def main() -> None:
    key = load_api_key()
    fred = Fred(api_key=key)
    build_database(fred)


if __name__ == "__main__":
    main()
