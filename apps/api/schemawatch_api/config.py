from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_MIN_SEVERITIES = frozenset({"breaking", "warning", "info"})


class Settings(BaseSettings):
    """Configuration for schemawatch API server, loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SCHEMAWATCH_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./schemawatch.db",
        description="Database connection URL (SQLite default, PostgreSQL supported)",
    )
    redis_url: str | None = Field(
        default=None,
        description="Optional Redis connection URL for deduplication and caching",
    )
    api_token: str = Field(
        default="",
        description="Bearer token required for API authentication unless dev_mode is true",
    )
    dev_mode: bool = Field(
        default=False,
        description="Enable developer mode (allows unauthenticated access when api_token is unset)",
    )
    learn_samples: int = Field(
        default=10,
        description="Number of initial samples required to establish a baseline",
    )
    sample_rate: float = Field(
        default=1.0,
        description="Sampling rate for post-learning observations (0.0 to 1.0)",
    )
    cooldown_seconds: int = Field(
        default=3600,
        description="Alert deduplication cooldown period in seconds",
    )
    slack_webhook_url: str | None = Field(
        default=None,
        description="Optional Slack webhook URL for drift alert dispatch",
    )
    alert_webhook_url: str | None = Field(
        default=None,
        description="Optional generic webhook URL for drift alert dispatch",
    )
    min_alert_severity: str = Field(
        default="info",
        description="Minimum severity required for alerts (breaking, warning, info)",
    )
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Allowed CORS origins list. CORS is disabled if empty",
    )
    max_ingest_body_bytes: int = Field(
        default=1_000_000,
        description="Maximum allowed request payload size in bytes for /api/ingest",
    )

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, v: str, info: Any) -> str:
        # If DEV_MODE is not true, API_TOKEN must not be empty
        # Handled in model validator below
        return v

    @field_validator("min_alert_severity")
    @classmethod
    def validate_min_severity(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in VALID_MIN_SEVERITIES:
            raise ValueError(f"min_alert_severity must be one of {sorted(VALID_MIN_SEVERITIES)}")
        return v_lower

    def validate_token_requirement(self) -> None:
        """Check that api_token is set when dev_mode is false."""
        if not self.dev_mode and not self.api_token:
            raise ValueError("SCHEMAWATCH_API_TOKEN is required when SCHEMAWATCH_DEV_MODE is false")
