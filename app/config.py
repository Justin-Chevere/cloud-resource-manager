from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Env vars (or a .env file) override these defaults, so the same code runs
    # against SQLite locally and Postgres in a deployed environment.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "cloud-control-plane"
    database_url: str = "sqlite:///./controlplane.db"

    reconciler_enabled: bool = True
    reconcile_interval_seconds: float = 2.0
    runtime: Literal["fake"] = "fake"


@lru_cache
def get_settings() -> Settings:
    return Settings()
