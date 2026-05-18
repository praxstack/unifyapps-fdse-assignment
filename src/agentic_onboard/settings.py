"""Application settings, loaded once from env / .env via Pydantic Settings.

Single source of truth for every tunable knob in the pipeline. Tests construct
their own ``Settings`` instances rather than mutating module-level state.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from env vars (or ``.env`` in dev).

    Resilience knobs are deliberately *small* defaults — the demo runs in
    seconds, not minutes. Tests override them via constructor kwargs to
    exercise edge cases without slowing the suite down.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---
    llm_provider: Literal["openrouter", "mock"] = Field(
        default="mock",
        description="`openrouter` calls a real LLM; `mock` uses a deterministic regex parser.",
    )
    openrouter_api_key: SecretStr | None = Field(default=None)
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Mock CRM ---
    crm_base_url: str = "http://127.0.0.1:8765"
    crm_fault_rate_429: float = 0.10
    crm_fault_rate_503: float = 0.05
    crm_latency_ms_min: int = 20
    crm_latency_ms_max: int = 120

    # --- Resilience knobs ---
    retry_max_attempts: int = 5
    retry_initial_backoff_s: float = 0.5
    retry_max_backoff_s: float = 8.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_s: float = 15.0

    # --- Storage ---
    database_url: str = "sqlite:///data/onboard.db"

    # --- Logging ---
    log_level: str = "INFO"

    # --- HTTP client ---
    http_timeout_s: float = 5.0


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide ``Settings`` instance, constructing it on first use.

    Cached because reading ``.env`` and validating env vars is cheap but not free,
    and because we want every module to see the same values within one process.
    Use :func:`reset_settings` from tests to force a re-read.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Test helper. Drops the cached settings so the next ``get_settings()`` re-reads env."""
    global _settings
    _settings = None
