"""config.Settings: required values, defaults, and the readable startup error."""
import pytest

from config import load_settings

# Every test builds Settings from explicit environment variables only, with
# the .env file switched off, so results don't depend on the machine.
BASE_ENV = {
    "DB_USER": "u", "DB_PASSWORD": "p", "DB_HOST": "h", "DB_PORT": "5432",
    "DB_NAME": "d", "SECRET_KEY": "s3cret",
}
ALL_KEYS = [*BASE_ENV, "ACCESS_TOKEN_EXPIRE_MINUTES", "TABLEAU_SERVER_URL", "TABLEAU_SITENAME",
            "TABLEAU_TOKEN_NAME", "TABLEAU_TOKEN_VALUE", "TABLEAU_PROJECT_NAME"]


@pytest.fixture
def env(monkeypatch):
    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in BASE_ENV.items():
        monkeypatch.setenv(key, value)

    def build(**changes):
        for key, value in changes.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        return load_settings(_env_file=None)
    return build


def test_defaults(env):
    s = env()
    assert s.access_token_expire_minutes == 30
    assert s.tableau_project_name == "Finance App 2026"
    assert s.db_port == 5432


def test_overrides(env):
    s = env(TABLEAU_PROJECT_NAME="Other Project", ACCESS_TOKEN_EXPIRE_MINUTES="5", DB_PORT="6543")
    assert s.tableau_project_name == "Other Project"
    assert s.access_token_expire_minutes == 5
    assert s.db_port == 6543


@pytest.mark.parametrize("missing", ["SECRET_KEY", "DB_USER", "DB_HOST", "DB_NAME"])
def test_missing_required_value_names_it(env, missing):
    with pytest.raises(RuntimeError, match=missing):
        env(**{missing: None})


def test_missing_secret_key_explains_how_to_generate_one(env):
    with pytest.raises(RuntimeError, match="secrets.token_urlsafe"):
        env(SECRET_KEY=None)


def test_blank_secret_key_is_rejected(env):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        env(SECRET_KEY="   ")


def test_bad_port_is_rejected(env):
    with pytest.raises(RuntimeError, match="DB_PORT"):
        env(DB_PORT="not-a-number")


def test_password_is_optional(env):
    # CI's throwaway Postgres uses trust auth, with no password.
    s = env(DB_PASSWORD=None)
    assert s.database_url == "postgresql://u@h:5432/d"


def test_database_url_escapes_special_characters(env):
    s = env(DB_PASSWORD="p@ss:w/rd%")
    assert s.database_url == "postgresql://u:p%40ss%3Aw%2Frd%25@h:5432/d"


def test_secrets_are_masked_in_repr(env):
    s = env(SECRET_KEY="zz-secret-key-zz", DB_PASSWORD="zz-db-pass-zz", TABLEAU_TOKEN_VALUE="zz-tableau-token-zz")
    for secret in ("zz-secret-key-zz", "zz-db-pass-zz", "zz-tableau-token-zz"):
        assert secret not in repr(s)


def test_require_tableau_names_every_missing_variable(env):
    s = env(TABLEAU_SERVER_URL="https://x", TABLEAU_SITENAME=None, TABLEAU_TOKEN_NAME="n", TABLEAU_TOKEN_VALUE=None)
    with pytest.raises(ValueError) as exc:
        s.require_tableau()
    assert "TABLEAU_SITENAME" in str(exc.value) and "TABLEAU_TOKEN_VALUE" in str(exc.value)
    assert "TABLEAU_SERVER_URL" not in str(exc.value)


def test_require_tableau_passes_when_complete(env):
    env(TABLEAU_SERVER_URL="https://x", TABLEAU_SITENAME="s",
        TABLEAU_TOKEN_NAME="n", TABLEAU_TOKEN_VALUE="v").require_tableau()
