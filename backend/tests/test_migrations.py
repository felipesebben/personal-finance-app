"""Migrations whose downgrade has to rebuild data, exercised on real rows."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

import database
from conftest import expenditure_payload

BACKEND_DIR = Path(__file__).resolve().parent.parent
DROP_IS_SHARED = "bc61f597d8fe"


def alembic_config():
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def fact_columns():
    return {c["name"] for c in inspect(database.engine).get_columns("fact_expenditures")}


def test_drop_is_shared_downgrade_rebuilds_the_flag_from_split_rows(client, household):
    def create(who, is_shared):
        resp = client.post("/expenditures/", headers=household[who],
                           json=expenditure_payload(household, is_shared=is_shared))
        assert resp.status_code == 200, resp.text

    create("a", True)    # shared: B holds a split row
    create("b", True)    # shared: A holds a split row
    create("a", False)   # personal: only A's 100% row

    assert "is_shared" not in fact_columns()

    cfg = alembic_config()
    database.engine.dispose()
    command.downgrade(cfg, f"{DROP_IS_SHARED}-1")
    try:
        assert "is_shared" in fact_columns()
        with database.engine.connect() as conn:
            flags = conn.execute(text(
                "SELECT is_shared FROM fact_expenditures ORDER BY expenditure_id"
            )).scalars().all()
        assert flags == [True, True, False]
    finally:
        # Always return the shared test database to head for the other tests.
        database.engine.dispose()
        command.upgrade(cfg, "head")

    assert "is_shared" not in fact_columns()
