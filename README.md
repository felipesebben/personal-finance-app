# Personal Finance App

A household expense tracker for two people, with analytics.

Each member of the household logs their own expenditures against a shared set of categories and payment methods. Everything lands in a PostgreSQL star schema, which is exported to Tableau Cloud and embedded back into the app as a dashboard — so the same data serves both day-to-day entry and month-over-month analysis.

> **Status:** in active development. Shared expenses are currently recorded as a boolean flag; income-proportional splitting between household members is designed but not yet implemented.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Streamlit (multipage) |
| API | FastAPI + SQLAlchemy, JWT auth |
| Database | PostgreSQL 15 (dimensional star schema) |
| Analytics | Tableau Cloud, via a `.hyper` extract published by an in-app ETL |
| Runtime | Docker Compose |
| Dependencies | Poetry, one project per service |

## Running it

Requires Docker and a `.env` file at the repo root (see [Configuration](#configuration)).

```bash
docker compose up --build
```

The backend applies any pending database migrations before it starts serving, so an empty volume builds itself.

| Service | URL |
| --- | --- |
| App (Streamlit) | http://localhost:8501 |
| API docs (Swagger) | http://localhost:8000/docs |
| pgAdmin | http://localhost:5050 |

Both application containers bind-mount their source, so code edits reload without a rebuild. Rebuild only after changing `pyproject.toml` or `poetry.lock`:

```bash
docker compose build --no-cache backend
```

### Running a service outside Docker

Each service is a self-contained Poetry project.

```bash
docker compose up -d db      # database only

cd backend  && poetry install && poetry run alembic upgrade head && poetry run uvicorn main:app --reload
cd frontend && poetry install && poetry run streamlit run Home.py
```

Note the `alembic upgrade head`: outside Compose nothing runs it for you, and the app no longer creates its own tables. The backend uses flat imports (`import models`), so it must be started from within `backend/`. It also reads `DB_HOST` from `.env` directly, which is set to `db` for the Compose workflow — that name only resolves inside the Compose network, so running the API on the host requires setting `DB_HOST=localhost` first.

## Configuration

All configuration comes from a single `.env` at the repo root. It is gitignored and must be created by hand:

```ini
# Database
DB_USER=
DB_PASSWORD=
DB_HOST=db            # the Compose service name; use "localhost" to run the API outside Docker
DB_PORT=5432
DB_NAME=

# Auth
SECRET_KEY=           # generate: python -c "import secrets; print(secrets.token_urlsafe(32))"

# pgAdmin
PGADMIN_DEFAULT_EMAIL=
PGADMIN_DEFAULT_PASSWORD=

# Tableau Cloud
TABLEAU_SERVER_URL=
TABLEAU_SITENAME=
TABLEAU_TOKEN_NAME=   # Personal Access Token
TABLEAU_TOKEN_VALUE=
TABLEAU_PROJECT_NAME=
```

## Data model

A dimensional star schema, defined in `backend/models.py` — that file is the single source of truth for the schema.

```
                 dim_user            dim_category
                     │                     │
                     └──── fact_expenditures ────┐
                                  │              │
                        dim_payment_method  (transaction_timestamp, price,
                                             nature, is_shared, installments)
```

Dimensions carry unique constraints on their natural keys, so a category is identified by `(primary_category, sub_category)` and a payment method by `(method_name, institution)`.

Timestamps are stored timezone-aware and converted to `America/Sao_Paulo` at the display and ETL boundaries.

## Analytics pipeline

`POST /refresh` (exposed as **Run ETL Pipeline** on the Manage Settings page) runs `backend/etl/main.py`:

1. **Extract** — join the fact to its dimensions, converting timestamps to local time.
2. **Transform** — `pantab` writes a `.hyper` extract to `artifacts/`.
3. **Publish** — `tableauserverclient` signs in with a Personal Access Token and overwrites the datasource on Tableau Cloud.

The Analytics page then embeds the published dashboard in an iframe.

## Project layout

```
backend/          FastAPI service
  main.py           routes, auth dependency, DB session
  models.py         SQLAlchemy ORM — source of truth for the schema
  schemas.py        Pydantic request/response contracts
  auth.py           bcrypt hashing, JWT minting
  alembic/          migrations — versions/ holds the revision chain
  etl/              Tableau extract + publish
frontend/         Streamlit app
  Home.py           login / signup
  pages/            Tracker, Analytics, Manage Settings
database/         legacy SQL — not executed, see CLAUDE.md
docker-compose.yml
```

## Development

Work happens on branches off `develop` and merges to `main` via pull request.

```
main ← develop ← feature/… | fix/… | chore/…
```

### Schema changes

The database schema is versioned with [Alembic](https://alembic.sqlalchemy.org/). `backend/models.py` remains the source of truth for what the schema *should* be; the revisions in `backend/alembic/versions/` are the record of how it got there. The backend container runs `alembic upgrade head` on startup, so a fresh volume migrates itself.

To change the schema:

```bash
# 1. edit backend/models.py
# 2. generate a revision from the difference
docker compose exec backend alembic revision --autogenerate -m "add whatever"
# 3. READ the generated file in backend/alembic/versions/ before running it
# 4. apply it
docker compose exec backend alembic upgrade head
```

Step 3 is not optional. Autogenerate compares your models to the live database and infers operations from the difference — it cannot tell a rename from a drop-and-add, and it does not know that `default=` in `models.py` is applied by Python rather than by Postgres, so new columns arrive as NULL on existing rows unless the migration backfills them.

The first revision was stamped onto the pre-existing database rather than executed against it, so it has never actually run here. After changing it, verify it still builds a correct database from nothing:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE fresh_check;"'
docker compose exec -e DB_NAME=fresh_check backend alembic upgrade head
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --schema-only --no-owner fresh_check'
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE fresh_check;"'
```

The result must match the schema of the real database.

## License

See [LICENSE](LICENSE).
