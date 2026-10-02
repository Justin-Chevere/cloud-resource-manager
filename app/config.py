import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Env vars (or a .env file) override these defaults, so the same code runs
    # against SQLite locally and Postgres in a deployed environment.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "cloud-resource-manager"
    database_url: str = "sqlite:///./controlplane.db"

    # Signs login tokens. There is deliberately no fixed default (the repo is
    # public): unset, each process makes a random one, so logins reset on restart.
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32), min_length=32)
    access_token_minutes: int = Field(default=30, gt=0)

    # Brute-force protection for POST /auth/token: failed logins allowed per account
    # and per client address within the window. Further attempts get 429.
    login_max_failures_per_account: int = Field(default=5, gt=0)
    login_max_failures_per_client: int = Field(default=20, gt=0)
    login_failure_window_seconds: int = Field(default=900, gt=0)
    password_reset_minutes: int = Field(default=30, gt=0)

    reconciler_enabled: bool = True
    reconcile_interval_seconds: float = 2.0
    runtime: Literal["fake"] = "fake"


@lru_cache
def get_settings() -> Settings:
    return Settings()
