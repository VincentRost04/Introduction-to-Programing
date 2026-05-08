# Inflation Toolkit

A reusable Python toolkit for analyzing the evolution of US consumer prices
and their interaction with monetary policy, built on top of the FRED
(Federal Reserve Bank of St. Louis) database.

This is the repository for a group project in the *Introduction to Programming*
course (Spring 2026). The current scope covers the **data pipeline**:

1. **ETL**: retrieve seven monthly CPI series and the Federal Funds Rate
   from the FRED API and store them in a DuckDB database.

The Python class for analysis and the report notebooks will be added in
follow-up work.

---

## Research question

> *How did different categories of US consumer prices evolve during the
> COVID-19 inflation episode, how does this behavior differ from the
> pre-pandemic baseline and the post-peak normalization phase, and how did
> the Federal Reserve's policy rate respond?*

---

## Quick start

### Requirements
- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/) (package manager)
- A free **FRED API key** ([request here](https://fred.stlouisfed.org/docs/api/api_key.html))

### 1. Clone and install the environment
```bash
git clone <your-repository-url>
cd inflation_toolkit
uv sync
```
`uv sync` installs the exact package versions pinned in `uv.lock`.

### 2. Set up your API key
```bash
cp .env.example .env
# Then open .env and paste your FRED API key.
```

### 3. (Optional) Rebuild the database
The generated `data/fred.db` is committed, so you can skip this step. To
rebuild it from scratch:
```bash
uv run python data/fred.py
```

---

## Repository structure

```
inflation_toolkit/
├── .gitignore
├── .env.example           # template for the FRED API key
├── README.md              # this file
├── pyproject.toml         # uv project file (dependencies)
├── uv.lock                # pinned package versions
├── _quarto.yml            # Quarto project config
│
└── data/
    ├── fred.py            # one-time ETL: FRED API → DuckDB
    ├── er_diagram.md      # Mermaid ER diagram + notes
    ├── er_diagram.png     # rendered ER diagram (PNG)
    └── fred.db            # generated DuckDB database (committed)
```

---

## Data overview

Eight monthly FRED series (seven CPI sub-indices + the Federal Funds Rate),
covering January 1990 onwards.

### CPI series (index, 1982–84 = 100, seasonally adjusted)
Source: U.S. Bureau of Labor Statistics.

| FRED ID    | Category         | Description                        |
|------------|------------------|------------------------------------|
| CPIAUCSL   | `total`          | All items (headline CPI)           |
| CPILFESL   | `core`           | All items less food and energy     |
| CPIFABSL   | `food`           | Food and beverages                 |
| CPIHOSSL   | `housing`        | Housing                            |
| CPITRNSL   | `transportation` | Transportation                     |
| CPIMEDSL   | `medical`        | Medical care                       |
| CPIENGSL   | `energy`         | Energy                             |

### Monetary policy series (percent, monthly average)
Source: Federal Reserve Board (Board of Governors).

| FRED ID    | Category       | Description                          |
|------------|----------------|--------------------------------------|
| FEDFUNDS   | `policy_rate`  | Effective Federal Funds Rate         |

The schema is documented in [`data/er_diagram.md`](data/er_diagram.md)
(Mermaid) with a rendered PNG at [`data/er_diagram.png`](data/er_diagram.png).

---

## License and credits

Data is provided by the [Federal Reserve Bank of St. Louis (FRED)](https://fred.stlouisfed.org/)
under its terms of use. Original data is from the U.S. Bureau of Labor
Statistics (CPI series) and the Federal Reserve Board (Federal Funds Rate).

Project for the *Introduction to Programming* course,
Dr. Franziska Bender & Dr. Aurélien Sallin.
