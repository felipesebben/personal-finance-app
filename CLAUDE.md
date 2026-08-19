# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A household expense tracker: a Streamlit UI talks to a FastAPI backend over HTTP, which persists to a Postgres star schema, and an ETL step exports that schema to a Tableau Cloud datasource. Everything runs through `docker-compose.yml` (db, backend, frontend, pgadmin) with `.env` at the repo root supplying every credential.

## Product intent

Two people — the owner and his wife — each log their own expenditures, and the owner analyses them: the current month first, and increasingly month-over-month as history accumulates. Analytics is the point of the project, not a bolt-on, so weigh changes against whether they make the data easier to analyse over time.

Tableau is deliberate scope. The dev site and the embedded dashboard exist because learning Tableau is one of the project's goals; do not propose replacing it with an in-app charting library.

This is a learning project. The owner wants to be walked through changes and understand the trade-offs, not handed finished features — default to explaining and proposing sequenced steps, and check before implementing.

**Shared expenses are split by an income-derived proportion, not 50/50 — and the schema does not model this yet.** `FactExpenditure` records only `user_id` (who paid) and `is_shared` (Boolean). There is no percentage, no allocation, and no "who owes whom", which means every per-person total the app or Tableau currently reports attributes 100% of a shared cost to whoever paid. The design work for this lives in the gitignored `notes/` folder, which also holds the project review and roadmap; read `notes/README.md` before proposing schema changes.

## Commands

Docker is the primary workflow — both app containers bind-mount their source, so code edits hot-reload without a rebuild.

```powershell
docker compose up --build          # full stack: API :8000, UI :8501, pgAdmin :5050, Postgres on $DB_PORT
docker compose up -d db            # database only (e.g. to run backend locally)
docker compose logs -f backend     # tail one service
docker compose down -v             # DESTROY the postgres_data volume (see "Schema changes")
docker compose build --no-cache backend   # needed after editing pyproject.toml/poetry.lock
```

Running a service outside Docker (from `backend/` or `frontend/`, each has its own Poetry project and `.venv`):

```powershell
poetry install
poetry run uvicorn main:app --reload      # backend/ — imports are flat ("import models"), so cwd MUST be backend/
poetry run streamlit run Home.py          # frontend/
```

Note that outside Docker the backend reads `DB_HOST`/`DB_PORT` straight from `.env` (host-side values, port 5433), while inside Docker `docker-compose.yml` overrides them to `db:5432`.

Utility scripts:

```powershell
poetry run python init_db.py              # backend/ — CREATE DATABASE if absent; tables come from create_all
poetry run python -m etl.main             # backend/ — run the Tableau ETL directly (same code path as POST /refresh)
poetry run python etl/generate_data.py    # backend/ — seed 50 fake expenditures (STALE: see below)
```

There is no test suite, linter, or formatter configured in this repo. Do not invent commands for them.

## Architecture

**Request path.** Streamlit pages are pure HTTP clients — they hold no DB connection. `frontend/Home.py` posts to `/token`, stashes the JWT in `st.session_state["access_token"]`, and every page under `frontend/pages/` re-checks that key and calls `st.stop()` if missing. `API_BASE_URL` comes from the `API_URL` env var (`http://backend:8000` in compose, `http://localhost:8000` otherwise).

**Auth.** `backend/auth.py` does bcrypt hashing and HS256 JWT minting; `get_current_user` in `backend/main.py` decodes `sub` (the email) and re-fetches `DimUser`. `SECRET_KEY` falls back to a hardcoded dev string when unset, and tokens expire after 30 minutes — an expired token surfaces in the UI as a 401 that the pages translate to "Session Expired".

**Not every endpoint is protected.** Only the expenditure routes and nothing else depend on `get_current_user`. `/users/`, `/categories/`, `/payment_methods/` (GET, POST, DELETE) and `/refresh` are open; the frontend sends the auth header to them anyway, so absence of a 401 there is expected, not a sign the header worked.

**Ownership model.** `POST /expenditures/` deliberately strips `user_id` from the request body (`model_dump(exclude={"user_id"})`) and substitutes `current_user.user_id` — the frontend still sends a dummy `"user_id": 0`. Reads and deletes are gated by `user_id == current_user OR is_shared == True`, so a shared household expense is visible and deletable by any logged-in user. Keep that `or_` filter intact when adding expenditure endpoints.

**Star schema.** `backend/models.py` defines `DimUser`, `DimCategory` (unique on primary+sub), `DimPaymentMethod` (unique on method+institution), and `FactExpenditure`. `schemas.py` mirrors them for Pydantic; `ExpenditureRead` nests the three dimension objects, which is why the read query uses `joinedload` and why the Tracker page reads dotted columns like `category.primary_category` after `pd.json_normalize`.

**ETL.** `POST /refresh` calls `etl.main.run_pipeline()` synchronously inside the request: SQL join → pandas → `pantab` writes `artifacts/expenditures.hyper` (relative to cwd, i.e. `backend/artifacts/` in the container) → `etl/tableau_manager.py` signs in with a Personal Access Token and publishes with `Overwrite` into the project named in `run_pipeline` (currently hardcoded `"Finance App 2026"`, *not* the `TABLEAU_PROJECT_NAME` env var). The Analytics page just iframes a hardcoded Tableau Cloud URL. A publish failure re-raises so the endpoint returns 500.

## Schema changes

There is no Alembic or any migration tool. Tables are created by `models.Base.metadata.create_all(bind=engine)` at backend import time, which **creates missing tables but never alters existing ones**. Adding a column to `models.py` therefore has no effect on a database that already has the table — the app will fail at query time with an undefined-column error. Either apply the `ALTER TABLE` by hand (pgAdmin at :5050) or `docker compose down -v` to drop the volume and rebuild from scratch.

`database/init.sql` is legacy and misleading: it is not mounted into the db container by `docker-compose.yml`, it still models the pre-auth `Dim_Person`/`PersonID` design that `models.py` replaced with `DimUser`/`user_id`, and it contains SQL that would not parse (`TIMESTAMPZ`, a missing comma after `CostType`). `backend/etl/generate_data.py` is stale for the same reason — it queries `dim_person` and `dim_paymentmethod`, neither of which exists. Treat `models.py` as the single source of truth for the schema.

## Conventions

- Timestamps are stored as `DateTime(timezone=True)`. The frontend attaches `America/Sao_Paulo` on write, and on read localizes naive values to UTC before converting back to São Paulo for display. The ETL does the same conversion in SQL (`AT TIME ZONE 'America/Sao_Paulo'`).
- After any successful mutation the Streamlit pages call `st.cache_data.clear()` then `st.rerun()` — the `get_data` helpers are `@st.cache_data` and take the token as an argument so the cache keys on the session.
- Installments only surface in the UI when the selected payment method has `is_credit` true; otherwise `current_installment`/`total_installments` both default to 1.
- Deletes of dimension rows are expected to fail with a FK violation when records reference them; the endpoints catch that, roll back, and return a 400 with a human-readable message.
