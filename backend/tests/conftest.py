"""
Shared fixtures for the backend test suite.

The API tests run against a real Postgres database, not SQLite: the app
relies on Numeric money, timezone-aware timestamps and ON DELETE CASCADE,
all of which SQLite would quietly fake. The test database is created from
scratch and built with `alembic upgrade head`, so every run also proves the
migration chain works on an empty database.
"""
import os

# Point the app at a dedicated test database BEFORE anything imports
# `config`/`database`, which read settings and build the engine at import
# time. pydantic-settings ranks real environment variables above the .env
# file, so this wins over .env.
os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", f"{os.environ.get('DB_NAME', 'finance')}_test")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")

from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

import database

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Drops and recreates the test database, then migrates it to head."""
    db_name = database.DB_NAME
    # Guard against ever pointing the destructive setup at real data.
    assert db_name.endswith("_test"), f"Refusing to run tests against non-test database {db_name!r}"

    admin_url = database.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")

    yield

    database.engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(autouse=True)
def clean_tables(request):
    """Empties every app table after each test, so tests never see each other's rows."""
    yield
    if "client" not in request.fixturenames:
        return
    with database.engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE fact_settlement, fact_expenditure_split, fact_expenditures, household_setting, "
            "dim_category, dim_payment_method, dim_user RESTART IDENTITY CASCADE"
        ))


@pytest.fixture
def client():
    from main import app
    with TestClient(app) as c:
        yield c


# --- helpers for building up state through the public API ---------------

def signup_and_login(client, name):
    """Creates a user and returns (user_id, auth headers)."""
    email = f"{name}@example.com"
    resp = client.post("/users/", json={"full_name": name, "email": email, "password": "pw"})
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user_id"]
    token = client.post("/token", data={"username": email, "password": "pw"}).json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def household(client):
    """
    Two users with a 60/40 household ratio, one category and one payment
    method — the minimum needed to post an expenditure.
    """
    a_id, a_headers = signup_and_login(client, "alice")
    b_id, b_headers = signup_and_login(client, "bob")
    resp = client.put("/household_settings/", headers=a_headers, json={"settings": [
        {"user_id": a_id, "share_pct": "0.6"},
        {"user_id": b_id, "share_pct": "0.4"},
    ]})
    assert resp.status_code == 200, resp.text
    category_id = client.post("/categories/", headers=a_headers, json={
        "primary_category": "Food", "sub_category": "Groceries",
    }).json()["category_id"]
    payment_method_id = client.post("/payment_methods/", headers=a_headers, json={
        "method_name": "Pix",
    }).json()["payment_method_id"]
    return {
        "a_id": a_id, "a": a_headers,
        "b_id": b_id, "b": b_headers,
        "category_id": category_id, "payment_method_id": payment_method_id,
    }


def expenditure_payload(household, price="100.00", is_shared=True, **extra):
    return {
        "transaction_timestamp": "2026-10-08T12:00:00-03:00",
        "price": price,
        "category_id": household["category_id"],
        "payment_method_id": household["payment_method_id"],
        "is_shared": is_shared,
        **extra,
    }


def splits_for(expenditure_id):
    """Allocation rows for one expenditure, read straight from the database."""
    with database.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT user_id, share_pct, share_amount, split_source "
            "FROM fact_expenditure_split WHERE expenditure_id = :id ORDER BY user_id"
        ), {"id": expenditure_id}).mappings().all()
    return [dict(r) for r in rows]
