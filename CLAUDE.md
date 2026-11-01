# CajuBills

Personal finance tool (Brazilian context, BRL/USD). It ingests investment data from a Google Sheet and bank/credit-card OFX exports, stores everything in a local SQLite DB, and shows it in Streamlit dashboards.

## Layout

- `run.py` — main pipeline entry point (investments, then spending). Run from the repo root: `python run.py`.
- `src/sql/` — `connection.py` (`db_connect("local"|"remote")`, `run_query`), `database_setup.py` (DDL + create/reset DB), `create_tables.py`.
- `src/backend/investments/`
  - `sheets.py` — reads the Google Sheet **"RSU + ETF"** via gspread (service account key `resources/google_sheets_key.json`, git-ignored). Tabs: `01 - Stock Trade`, `02 - Fixed Income`, `03 - FGTS`, `04 - CDI`, `05 - IPCA`, `06 - Target`.
  - `raw_data.py` — `upsert_raw_data`: **deletes and reloads** the operations tables (`variable_income_operations`, `fixed_income_operations`, `fgts_operations`, `target_percentage`) from the sheet. Appends CDI/IPCA to `index_series` (INSERT OR IGNORE).
  - `asset_pricing.py` — `update_asset_price`: finds missing price ranges per ticker (plus `BRL=X` FX) and fetches them from yfinance into `asset_price`.
  - `preprocessing.py` — builds derived tables (`dates`, `daily_asset_price`, `*_daily_balance`, `daily_balance`, `operations`, `financial_returns`, `summary_returns`) with SQL.
  - `constants.py` — sheet/tab names, hardcoded `NU_PRICES` (NU stock quarterly prices), targets.
- `src/backend/spending/` — `ofx_parser.py` parses all OFX files under `resources/files/{credit_card,nuconta}`, categorizes them (`categorization_rules.py` + `resources/user_defined_categories.csv`), and writes to `ofx_transactions`.
- `src/frontend/` — Streamlit app: `app.py`, `pages/1_Investments_Dashboard.py`, `pages/2_Transaction_Editor_DB.py` (manual re-categorization, budget via `resources/user_defined_budget.csv`).
- `src/history_dashboard.py` — extra history dashboard.
- `migrate_rds_to_local.py` — one-off script copying `asset_price` from the old RDS MySQL to local SQLite.
- `resources/db/cajubills_local.db` — the SQLite DB (**committed to git**, so it shows as modified after each refresh).
- `resources/files/` — raw inputs: `credit_card/nubank-YYYY-MM.ofx`, `nuconta/nubank-YYYY-MM.ofx`, plus CDI/IPCA downloads, E*Trade benefit history and trade confirmations (reference material used to fill the sheet).
- `resources/*.csv` — `target_percentages`, `user_defined_budget`, `user_defined_categories`.

## Recurring workflow (periodic data refresh)

1. Update the Google Sheet "RSU + ETF" (new trades, fixed income, FGTS, CDI/IPCA rows, targets). Sheet columns are read by name in `sheets.py`; don't rename them.
2. Download the new Nubank OFX files and drop them in `resources/files/credit_card/` and `resources/files/nuconta/` as `nubank-YYYY-MM.ofx`.
3. Run `python run.py` to reload investments (sheet → DB, yfinance prices, derived tables) and spending (OFX → categorized transactions).
4. Run `streamlit run src/frontend/app.py` to review; fix uncategorized transactions in the Transaction Editor page.
5. Commit the new OFX files and updated `cajubills_local.db` (branches are typically named like `<name>-update`, merged via PR to `main`).

Occasional: update year-specific constants (e.g. `NU_PRICES`, target allocations in `constants.py`/`src/contants.py`), and add rules to `categorization_rules.py` when new merchants show up.

## Setup

- Python version in `.python-version`; `pip install -r requirements.txt`.
- Needs `resources/google_sheets_key.json` locally (not in git).
- Imports assume `src/` is on `sys.path` (`run.py` handles this; modules use `from backend...` / `from sql...`).

## Gotchas

- `run.py` has the DB reset commented out; it only runs `create_tables_from_ddl()` then reloads. Raw operation tables are fully replaced from the sheet each run, so the sheet is the source of truth for investments.
- `preprocessing.py` uses SQLite-only syntax (`INSERT OR IGNORE`, `?` placeholders); `raw_data.py` also supports MySQL.
- `src/sql/connection.py` has the remote RDS host and **password hardcoded in plain text** and committed — should be moved to env vars / rotated.
- No tests in the repo.
