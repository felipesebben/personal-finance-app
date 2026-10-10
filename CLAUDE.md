# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A household expense tracker: a Streamlit UI talks to a FastAPI backend over HTTP, which persists to a Postgres star schema, and an ETL step exports that schema to a Tableau Cloud datasource. Everything runs through `docker-compose.yml` (db, backend, frontend, pgadmin) with `.env` at the repo root supplying every credential.

## Product intent

Two people — the owner and his wife — each log their own expenditures, and the owner analyses them: the current month first, and increasingly month-over-month as history accumulates. Analytics is the point of the project, not a bolt-on, so weigh changes against whether they make the data easier to analyse over time.

Tableau is deliberate scope. The dev site and the embedded dashboard exist because learning Tableau is one of the project's goals; do not propose replacing it with an in-app charting library.

This is a learning project. The owner wants to be walked through changes and understand the trade-offs, not handed finished features — default to explaining and proposing sequenced steps, and check before implementing.

**Shared expenses are split by an income-derived proportion, not 50/50.** `FactExpenditure.user_id` is who *paid*; who *bears* the cost lives in `fact_expenditure_split` (one row per person per expense, `share_pct` and `share_amount` snapshotted at write time from `household_setting`). Per-person spending must be computed from the split table, not from `FactExpenditure.user_id`. In Tableau, per-person analysis belongs on the `allocations` datasource; the older `expenditures` datasource still attributes 100% of a shared cost to the payer. The design work lives in the gitignored `notes/` folder, which also holds the project review and roadmap; read `notes/README.md` before proposing schema changes.

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
poetry run python seed.py                 # backend/ — seed months of demo history (--months, --random-seed, --append)
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

**Configuration.** Every backend setting goes through `backend/config.py`: a pydantic-settings `Settings` built once at import (`from config import settings`), reading environment variables first and then the repo-root `.env`. Required values (DB_*, `SECRET_KEY`) fail at startup with the variable named; Tableau credentials are optional until `settings.require_tableau()` runs at publish time, so tests and CI don't need them. Don't add new `os.getenv` calls — add a field to `Settings` and a line to `.env.example`. The ETL reuses `database.engine` rather than building its own connection. The frontend's one setting, `API_URL`, is read in `frontend/config.py` and imported by every page as `API_BASE_URL`.

**Request path.** Streamlit pages are pure HTTP clients — they hold no DB connection. `frontend/Home.py` posts to `/token`, stashes the JWT in `st.session_state["access_token"]`, and every page under `frontend/pages/` re-checks that key and calls `st.stop()` if missing. `API_BASE_URL` comes from `frontend/config.py`, which reads the `API_URL` env var (`http://backend:8000` in compose, `http://localhost:8000` otherwise).

**Auth.** `backend/auth.py` does bcrypt hashing and HS256 JWT minting; `get_current_user` in `backend/main.py` decodes `sub` (the email) and re-fetches `DimUser`. `SECRET_KEY` is required (startup fails without it), and tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30) — an expired token surfaces in the UI as a 401 that the pages translate to "Session Expired".

**Every route except signup and login requires a token.** `POST /users/` and `POST /token` are public; everything else depends on `get_current_user`, either as a parameter (when the handler needs the user) or via `dependencies=[Depends(get_current_user)]`. `tests/test_auth.py` keeps a list of protected routes and checks each rejects a missing or invalid token — add new routes to it.

**Ownership model.** `POST /expenditures/` deliberately strips `user_id` from the request body (`model_dump(exclude={"user_id"})`) and substitutes `current_user.user_id` — the frontend still sends a dummy `"user_id": 0`. Reads and deletes go through `visible_to(user)` in `main.py`: the user paid it, **or** holds a split row for it. So a shared expense is visible and deletable by both household members, and an account outside the household sees none of the household's expenses. Use `visible_to` for any new expenditure endpoint.

**"Shared" is derived, not stored.** `FactExpenditure.has_other_share` (a `column_property` in `models.py`) is true when someone other than the payer holds a split row; `/summary/`, `ExpenditureRead.is_shared` and the ETL's `is_shared` column all read it. The request field `is_shared` on `POST /expenditures/` now only means "split this by the household ratio". There is no `is_shared` column: migration `bc61f597d8fe` dropped it (its downgrade rebuilds the column from the split rows, covered by `tests/test_migrations.py`), and `POST /expenditures/` excludes the field from the row it writes.

**Star schema.** `backend/models.py` defines `DimUser`, `DimCategory` (unique on primary+sub), `DimPaymentMethod` (unique on method+institution), and `FactExpenditure`. `schemas.py` mirrors them for Pydantic; `ExpenditureRead` nests the three dimension objects, which is why the read query uses `joinedload` and why the Tracker page reads dotted columns like `category.primary_category` after `pd.json_normalize`.

**Splits and balances.** `POST /expenditures/` writes the expenditure and its split rows in one transaction through `ledger.add_expenditure` (which flushes but never commits, and is also what `seed.py` uses), splitting with the pure `split_logic.split_amount` (last share absorbs the rounding remainder, so parts always sum to the price). `GET /balances/?month=YYYY-MM` reports paid / borne / net per person and the settling transfers (pure `split_logic.settle`). It counts only expenses with a split row for someone other than the payer, so one person's personal spending never appears in the other's view; months are São Paulo calendar months.

**Settlements.** `fact_settlement` records money moved between members to square up (`/settlements/` POST, GET, DELETE; only the payer or payee may record or delete one). `/balances/` folds them in: net = paid − borne + settled_out − settled_in. A settlement's `period_month` (the month it squares up, set from the Tracker's selected period) is deliberately separate from `settled_at` (when the money moved), because October is usually paid back in November; month views filter on `period_month`, and a settlement with `period_month` NULL counts only towards the all-time balance. The ETL publishes them as the `settlements` datasource.

Keep arithmetic in `split_logic.py`, free of DB access, so it stays unit-testable.

**Monthly summary.** `GET /summary/?month=YYYY-MM` (defaults to the current São Paulo month) is from the logged-in user's point of view: their total borne (share of shared + personal) against the previous month, the household's shared total, and their spending by primary category and cost type. It deliberately never exposes the other person's personal spending; cross-person analysis belongs in Tableau. The Tracker page's "Monthly Overview" section drives both `/summary/` and `/balances/` from one period picker.

**ETL.** `POST /refresh` calls `etl.main.run_pipeline()` synchronously inside the request: SQL joins → pandas → `pantab` writes one Hyper file per datasource under `artifacts/` (relative to cwd, i.e. `backend/artifacts/` in the container) → `etl/tableau_manager.py` signs in with a Personal Access Token and publishes each with `Overwrite` into `settings.tableau_project_name` (`TABLEAU_PROJECT_NAME`, default `"Finance App 2026"`) — a wrong value silently publishes into another project, leaving the workbook stale. The Tableau datasource name comes from the file name:

- `expenditures` — one row per expense, `price` attributed to the payer. Kept unchanged so existing workbooks keep working.
- `allocations` — one row per person per expense from `fact_expenditure_split`: `borne_by`, `paid_by`, `share_pct`, `share_amount`, `split_source`, `month_start` (São Paulo), plus category/payment/installment columns. Per-person analysis should `SUM(share_amount)` here. `expense_total` repeats the full price on every row of an expense, so never sum it.
- `settlements` — one row per payment between members: `settled_at`, `settled_month_start`, `period_month` (the month it squares up; NULL = all-time), `from_name`, `to_name`, `amount`, `note`, `recorded_by`. Kept out of the spending grain because it moves money rather than spending it.

A datasource with no rows is skipped rather than published empty.

`generate_hyper_file` casts all-NULL *untyped* columns to text, because Hyper rejects a column whose type can't be inferred. Date columns that may be entirely NULL must be pinned with `pd.to_datetime` in their extract, or they publish as text and flip type on a later refresh, which breaks workbooks. The Analytics page just iframes a hardcoded Tableau Cloud URL. A publish failure re-raises so the endpoint returns 500.

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

The dumped schema must match the live database. The full procedure — including the review checklist for generated revisions and a `diff` that ignores `pg_dump`'s random `\restrict` keys — is the `schema-change` skill in `.claude/skills/`. `-e DB_NAME=...` works because `config.Settings` ranks real environment variables above the `.env` file.

Treat `models.py` as the single source of truth for the schema.

## Conventions

- Timestamps are stored as `DateTime(timezone=True)`. The frontend attaches `America/Sao_Paulo` on write, and on read localizes naive values to UTC before converting back to São Paulo for display. The ETL does the same conversion in SQL (`AT TIME ZONE 'America/Sao_Paulo'`).
- After any successful mutation the Streamlit pages call `st.cache_data.clear()` then `st.rerun()` — the `get_data` helpers are `@st.cache_data` and take the token as an argument so the cache keys on the session.
- Installments only surface in the UI when the selected payment method has `is_credit` true; otherwise `current_installment`/`total_installments` both default to 1.
- Deletes of dimension rows are expected to fail with a FK violation when records reference them; the endpoints catch that, roll back, and return a 400 with a human-readable message.
