"""Application settings (ADHKAR_* env prefix + 12-factor DATABASE_URL/REDIS_URL)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADHKAR_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # ----- core -----
    env: Literal["dev", "test", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = Field(min_length=1)
    cors_origins: list[str] = ["http://localhost:5173"]

    # ----- database (also supports DATABASE_URL 12-factor without ADHKAR_ prefix) -----
    database_url: str = Field(validation_alias="DATABASE_URL")

    # ----- redis -----
    redis_url: str = Field(validation_alias="REDIS_URL")

    # ----- s3 / minio -----
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minio-dev"
    s3_secret_key: str = "minio-dev-secret"  # noqa: S105  # dev-only placeholder; overridden via env in non-dev
    s3_bucket: str = "adhkar-attachments"
    s3_region: str = "us-east-1"

    # ----- av webhook -----
    av_webhook_secret: str = ""  # empty disables /v1/attachments/av-scan-webhook

    # ----- smtp (dev = mailhog) -----
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from: str = "adhkar@localhost"

    # ----- otel -----
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "adhkar-api"

    # ----- build metadata -----
    git_commit: str = "unknown"
    built_at: str = "unknown"

    # ----- migrations -----
    skip_migrations: bool = False

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("ADHKAR_SECRET_KEY must be at least 32 characters")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
