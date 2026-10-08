# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A household expense tracker: a Streamlit UI talks to a FastAPI backend over HTTP, which persists to a Postgres star schema, and an ETL step exports that schema to a Tableau Cloud datasource. Everything runs through `docker-compose.yml` (db, backend, frontend, pgadmin) with `.env` at the repo root supplying every credential.

## Product intent

Two people — the owner and his wife — each log their own expenditures, and the owner analyses them: the current month first, and increasingly month-over-month as history accumulates. Analytics is the point of the project, not a bolt-on, so weigh changes against whether they make the data easier to analyse over time.

Tableau is deliberate scope. The dev site and the embedded dashboard exist because learning Tableau is one of the project's goals; do not propose replacing it with an in-app charting library.

This is a learning project. The owner wants to be walked through changes and understand the trade-offs, not handed finished features — default to explaining and proposing sequenced steps, and check before implementing.

**Shared expenses are split by an income-derived proportion, not 50/50.** `FactExpenditure.user_id` is who *paid*; who *bears* the cost lives in `fact_expenditure_split` (one row per person per expense, `share_pct` and `share_amount` snapshotted at write time from `household_setting`). Per-person spending must be computed from the split table, not from `FactExpenditure.user_id`. The Tableau ETL does not use the split table yet, so its per-person totals still attribute 100% of a shared cost to the payer. The design work lives in the gitignored `notes/` folder, which also holds the project review and roadmap; read `notes/README.md` before proposing schema changes.

## Commands

Docker is the primary workflow — both app containers bind-mount their source, so code edits hot-reload without a rebuild.

```powershell
docker compose up --build          # full stack: API :8000, UI :8501, pgAdmin :5050, Postgres on $DB_PORT
docker compose up -d db            # database only (e.g. to run backend locally)
docker compose logs -f backend     # tail one service
docker compose down -v             # DESTROY the postgres_data volume (Alembic rebuilds it on next start)
docker compose build --no-cache backend   # needed after editing pyproject.toml/poetry.lock
```

Running a service outside Docker (from `backend/` or `frontend/`, each has its own Poetry project and `.venv`):

```powershell
poetry install
poetry run uvicorn main:app --reload      # backend/ — imports are flat ("import models"), so cwd MUST be backend/
poetry run streamlit run Home.py          # frontend/
```

Note that outside Docker the backend reads `DB_HOST`/`DB_PORT` straight from `.env`, which currently holds the Compose values (`db` / `5432`) — running the API on the host therefore requires setting `DB_HOST=localhost` first. Inside Docker, `docker-compose.yml` overrides them to `db:5432` regardless.

Utility scripts:

```powershell
poetry run python init_db.py              # backend/ — CREATE DATABASE if absent; tables come from Alembic
poetry run python -m etl.main             # backend/ — run the Tableau ETL directly (same code path as POST /refresh)
poetry run python etl/generate_data.py    # backend/ — seed 50 fake expenditures (STALE: see below)
```

Migrations run inside the backend container, where `DB_HOST=db` resolves:

```powershell
docker compose exec backend alembic current                      # which revision the DB is on
docker compose exec backend alembic history                      # the revision chain
docker compose exec backend alembic revision --autogenerate -m "what changed"
docker compose exec backend alembic upgrade head                 # apply
docker compose exec backend alembic downgrade -1                 # step back one
```

Tests (pytest, in `backend/tests/`) run inside the backend container:

```powershell
docker compose exec backend pytest                                   # whole suite
docker compose exec backend pytest tests/test_split_logic.py -v      # one file
```

API tests hit a real Postgres, never SQLite. `tests/conftest.py` points `DB_NAME` at `<DB_NAME>_test` (or `$TEST_DB_NAME`) before anything imports `database`, drops and recreates that database, migrates it with `alembic upgrade head`, truncates every table after each API test, and drops the database at the end. It refuses to run against a name not ending in `_test`. GitHub Actions (`.github/workflows/ci.yml`) runs the same suite against a Postgres service container on every push and PR to `develop`/`main`. Every PR should add tests for what it changes.

There is no linter or formatter configured. Do not invent commands for them.

## Architecture

**Request path.** Streamlit pages are pure HTTP clients — they hold no DB connection. `frontend/Home.py` posts to `/token`, stashes the JWT in `st.session_state["access_token"]`, and every page under `frontend/pages/` re-checks that key and calls `st.stop()` if missing. `API_BASE_URL` comes from the `API_URL` env var (`http://backend:8000` in compose, `http://localhost:8000` otherwise).

**Auth.** `backend/auth.py` does bcrypt hashing and HS256 JWT minting; `get_current_user` in `backend/main.py` decodes `sub` (the email) and re-fetches `DimUser`. `SECRET_KEY` falls back to a hardcoded dev string when unset, and tokens expire after 30 minutes — an expired token surfaces in the UI as a 401 that the pages translate to "Session Expired".

**Not every endpoint is protected.** Only the expenditure routes and nothing else depend on `get_current_user`. `/users/`, `/categories/`, `/payment_methods/` (GET, POST, DELETE) and `/refresh` are open; the frontend sends the auth header to them anyway, so absence of a 401 there is expected, not a sign the header worked.

**Ownership model.** `POST /expenditures/` deliberately strips `user_id` from the request body (`model_dump(exclude={"user_id"})`) and substitutes `current_user.user_id` — the frontend still sends a dummy `"user_id": 0`. Reads and deletes are gated by `user_id == current_user OR is_shared == True`, so a shared household expense is visible and deletable by any logged-in user. Keep that `or_` filter intact when adding expenditure endpoints.

**Star schema.** `backend/models.py` defines `DimUser`, `DimCategory` (unique on primary+sub), `DimPaymentMethod` (unique on method+institution), and `FactExpenditure`. `schemas.py` mirrors them for Pydantic; `ExpenditureRead` nests the three dimension objects, which is why the read query uses `joinedload` and why the Tracker page reads dotted columns like `category.primary_category` after `pd.json_normalize`.

**Splits and balances.** `POST /expenditures/` writes the expenditure and its split rows in one transaction, using the pure `split_logic.split_amount` (last share absorbs the rounding remainder, so parts always sum to the price). `GET /balances/?month=YYYY-MM` reports paid / borne / net per person and the settling transfers (pure `split_logic.settle`). It counts only expenses with a split row for someone other than the payer, so one person's personal spending never appears in the other's view; months are São Paulo calendar months. Keep arithmetic in `split_logic.py`, free of DB access, so it stays unit-testable.

**ETL.** `POST /refresh` calls `etl.main.run_pipeline()` synchronously inside the request: SQL joins → pandas → `pantab` writes two Hyper files under `artifacts/` (relative to cwd, i.e. `backend/artifacts/` in the container) → `etl/tableau_manager.py` signs in with a Personal Access Token and publishes each with `Overwrite` into the project named in `run_pipeline` (currently hardcoded `"Finance App 2026"`, *not* the `TABLEAU_PROJECT_NAME` env var, whose `.env` value is `Default` — switching to it would publish to the wrong project). The Tableau datasource name comes from the file name:

- `expenditures` — one row per expense, `price` attributed to the payer. Kept unchanged so existing workbooks keep working.
- `allocations` — one row per person per expense from `fact_expenditure_split`: `borne_by`, `paid_by`, `share_pct`, `share_amount`, `split_source`, `month_start` (São Paulo), plus category/payment/installment columns. Per-person analysis should `SUM(share_amount)` here. `expense_total` repeats the full price on every row of an expense, so never sum it.

`generate_hyper_file` casts all-NULL columns to text, because Hyper rejects a column whose type can't be inferred. The Analytics page just iframes a hardcoded Tableau Cloud URL. A publish failure re-raises so the endpoint returns 500.

## Schema changes

**Alembic owns the schema.** Migrations live in `backend/alembic/versions/`, and the backend container runs `alembic upgrade head` before starting uvicorn (the `command:` override on the `backend` service in `docker-compose.yml`), so a fresh volume migrates itself on `docker compose up`. There is no `create_all` call any more — do not add one back, or two systems create the same tables and `alembic_version` stops describing reality.

`alembic/env.py` sets `sqlalchemy.url` from `database.DATABASE_URL` rather than from `alembic.ini`, which keeps credentials out of a committed file; it imports `models` purely so `Base.metadata` is populated; and it sets `compare_type=True` so column type changes are detected at all.

To change the schema: edit `models.py`, autogenerate a revision, **read the generated file before running it**, then upgrade. Autogenerate is a diffing tool, not an oracle — it reads a rename as drop-then-add, and `default=` in `models.py` is a Python-side default that never reaches Postgres, so new columns arrive as NULL on existing rows unless the migration backfills them explicitly.

The first revision (`b24c43f3c0f3`, "baseline: existing schema") was **stamped, not executed**, on the existing database. It describes the pre-Alembic schema — including `price` as `Float`, which the next revision converts to `Numeric(10, 2)`. Because it never ran locally, bugs in it are invisible here. Validate any change to it by building a throwaway database from scratch:

```powershell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE fresh_check;"'
docker compose exec -e DB_NAME=fresh_check backend alembic upgrade head
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --schema-only --no-owner fresh_check'
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE fresh_check;"'
```

The dumped schema must match the live database. `-e DB_NAME=...` works because `database.py` reads that variable from the environment and `load_dotenv()` never overrides what is already set.

`database/init.sql` is legacy and misleading: it is not mounted into the db container by `docker-compose.yml`, it still models the pre-auth `Dim_Person`/`PersonID` design that `models.py` replaced with `DimUser`/`user_id`, and it contains SQL that would not parse (`TIMESTAMPZ`, a missing comma after `CostType`). `backend/etl/generate_data.py` is stale for the same reason — it queries `dim_person` and `dim_paymentmethod`, neither of which exists. Treat `models.py` as the single source of truth for the schema.

## Conventions

- Timestamps are stored as `DateTime(timezone=True)`. The frontend attaches `America/Sao_Paulo` on write, and on read localizes naive values to UTC before converting back to São Paulo for display. The ETL does the same conversion in SQL (`AT TIME ZONE 'America/Sao_Paulo'`).
- After any successful mutation the Streamlit pages call `st.cache_data.clear()` then `st.rerun()` — the `get_data` helpers are `@st.cache_data` and take the token as an argument so the cache keys on the session.
- Installments only surface in the UI when the selected payment method has `is_credit` true; otherwise `current_installment`/`total_installments` both default to 1.
- Deletes of dimension rows are expected to fail with a FK violation when records reference them; the endpoints catch that, roll back, and return a 400 with a human-readable message.
