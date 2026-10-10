"""
One typed, validated place for every backend setting.

Values come from environment variables first, then from the `.env` at the
repo root (Docker Compose passes that file in as environment variables, so
inside the container the file itself isn't needed). Anything required and
missing stops the app at import time with a message naming the variable,
rather than failing later at 2am inside the ETL.

Tableau credentials are optional here and checked only when publishing,
so tests and CI run without them.
"""
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # --- Database (required, except the password: CI uses trust auth) ---
    db_user: str
    db_password: SecretStr = SecretStr("")
    db_host: str
    db_port: int = 5432
    db_name: str

    # --- Auth ---
    secret_key: SecretStr
    access_token_expire_minutes: int = Field(30, gt=0)

    # --- Tableau (optional until publishing) ---
    tableau_server_url: str | None = None
    tableau_sitename: str | None = None
    tableau_token_name: str | None = None
    tableau_token_value: SecretStr | None = None
    tableau_project_name: str = "Finance App 2026"

    @field_validator("secret_key")
    @classmethod
    def secret_key_not_blank(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("must not be empty")
        return v

    @property
    def database_url(self) -> str:
        # URL.create escapes special characters in the password, which the
        # old hand-built f-string did not.
        return URL.create(
            "postgresql",
            username=self.db_user,
            password=self.db_password.get_secret_value() or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    def require_tableau(self) -> None:
        """Raises with every missing Tableau variable named, before signing in."""
        missing = [
            name.upper()
            for name in ("tableau_server_url", "tableau_sitename", "tableau_token_name", "tableau_token_value")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Missing Tableau settings: {', '.join(missing)} (see .env.example)")


def load_settings(**overrides) -> Settings:
    """Builds Settings, turning a validation error into a readable startup message."""
    try:
        return Settings(**overrides)
    except ValidationError as e:
        problems = "\n".join(
            f"  - {'_'.join(str(p) for p in err['loc']).upper()}: {err['msg']}" for err in e.errors()
        )
        hint = ""
        if any(err["loc"] == ("secret_key",) for err in e.errors()):
            hint = '\nGenerate a SECRET_KEY with:\n  python -c "import secrets; print(secrets.token_urlsafe(32))"'
        raise RuntimeError(
            f"Invalid configuration — set these in the environment or in the .env at the repo root "
            f"(see .env.example):\n{problems}{hint}"
        ) from None


settings = load_settings()
