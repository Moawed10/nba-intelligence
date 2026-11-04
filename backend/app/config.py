from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NBA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg:///nba_intelligence"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    log_level: str = "INFO"
    log_json: bool = True
    db_connect_timeout_seconds: int = 5
    db_pool_timeout_seconds: float = 10.0
    api_statement_timeout_ms: int = 15_000

    stats_request_interval_seconds: float = 1.0
    stats_timeout_seconds: float = 30.0
    stats_max_attempts: int = 5
    stats_backoff_base_seconds: float = 1.0
    stats_backoff_cap_seconds: float = 60.0
    stats_cache_dir: Path = Path(".cache/nba_stats")

    cors_origins: list[str] = []
    api_docs_enabled: bool = True
    api_cache_enabled: bool = True
    prediction_rate_per_minute: int = 60
    prediction_rate_burst: int = 20
    prediction_rate_global_per_minute: int = 600
    trusted_proxy_ips: list[str] = ["127.0.0.1", "::1"]

    first_season: int = 2018
    artifacts_dir: Path = Path("artifacts")
    photos_dir: Path = Path(".cache/photos")
    team_minutes_tolerance: int = 5

    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
