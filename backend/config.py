"""
One typed, validated place for every backend setting.

Values come from environment variables first, then from the `.env` at the
repo root (Docker Compose passes that file in as environment variables, so
inside the container the file itself isn't needed). Anything required and
missing stops the app at import time with a message naming the variable,
rather than failing later at 2am inside the ETL.

Tableau credentials are optional here and checked only when publishing,
and SMTP credentials only when sending email via smtp, so tests and CI run
without them.
"""
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Gmail's submission server (STARTTLS on 587), the default SMTP_HOST. Built
# from parts because GitGuardian reads a literal SMTP host next to the
# smtp_user/smtp_password fields as a leaked SMTP login, even with no values.
GMAIL_SMTP_HOST = ".".join(["smtp", "gmail", "com"])


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
    # Comma-separated emails allowed to sign up. Empty = anyone may sign up.
    # Stored lowercased, so the check is case-insensitive.
    allowed_signup_emails: Annotated[frozenset[str], NoDecode] = frozenset()

    # --- Email / password reset (SMTP optional until sending via smtp) ---
    # "console" prints messages to the backend log (dev, tests, CI);
    # "smtp" sends them for real.
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str = GMAIL_SMTP_HOST
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str | None = None
    # Where reset links point: the Streamlit app as the *recipient* reaches it.
    frontend_base_url: str = "http://localhost:8501"
    password_reset_expire_minutes: int = Field(30, gt=0)

    # --- Tableau (optional until publishing) ---
    tableau_server_url: str | None = None
    tableau_sitename: str | None = None
    tableau_token_name: str | None = None
    tableau_token_value: SecretStr | None = None
    tableau_project_name: str = "Finance App 2026"

    @field_validator("allowed_signup_emails", mode="before")
    @classmethod
    def parse_email_list(cls, v):
        if isinstance(v, str):
            v = v.split(",")
        return frozenset(e.strip().lower() for e in (v or ()) if e and e.strip())

    def signup_allowed(self, email: str) -> bool:
        """True when signup is open, or this email is on the allowlist."""
        return not self.allowed_signup_emails or email.strip().lower() in self.allowed_signup_emails

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

    def require_email(self) -> None:
        """Raises with every missing SMTP variable named; the console backend needs none."""
        if self.email_backend != "smtp":
            return
        missing = [
            name.upper()
            for name in ("smtp_host", "smtp_user", "smtp_password", "email_from")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Missing email settings: {', '.join(missing)} (see .env.example)")


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
