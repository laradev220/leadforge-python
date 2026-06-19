"""Pydantic-settings env loader. Mirrors TS packages/config/src/index.ts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Walk up from CWD to find .env (mirrors TS loadEnv)."""
    current = Path.cwd()
    root = Path(current.anchor)
    while current != root:
        candidate = current / ".env"
        if candidate.is_file():
            return str(candidate)
        current = current.parent
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    node_env: str = Field(default="development", alias="NODE_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5433/leadforge",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5433/leadforge",
        alias="DATABASE_URL_SYNC",
    )

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    jwt_secret: str = Field(default="dev-secret", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expires_hours: int = Field(default=24, alias="JWT_EXPIRES_HOURS")

    scraper_concurrency: int = Field(default=3, alias="SCRAPER_CONCURRENCY")
    scraper_request_delay_ms: int = Field(default=2000, alias="SCRAPER_REQUEST_DELAY_MS")
    scraper_request_timeout_ms: int = Field(default=10000, alias="SCRAPER_REQUEST_TIMEOUT_MS")
    scraper_max_results_per_search: int = Field(default=8, alias="SCRAPER_MAX_RESULTS_PER_SEARCH")
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")
    playwright_proxy_url: str = Field(default="", alias="PLAYWRIGHT_PROXY_URL")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    export_dir: str = Field(default="./exports", alias="EXPORT_DIR")

    # Comma-separated list of source labels to enable.  When empty all
    # sources registered in the source registry are used.
    # Format per country: ``PK=yellow_pages_pk,hotfrog_pk;US=yelp"
    enabled_sources: str = Field(default="", alias="ENABLED_SOURCES")

    @property
    def is_production(self) -> bool:
        return self.node_env.lower() == "production"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
