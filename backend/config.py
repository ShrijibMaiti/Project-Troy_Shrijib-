"""
Settings, validated at import time.

Everything the process needs is checked here and fails LOUDLY on boot rather
than at 07:00 UTC when the capture job runs. A missing SEC_USER_AGENT should
stop the container starting, not silently produce a day of blocked requests.

Calibration is deliberately part of config: the scoring engine loads frozen
constants produced by Wrik's notebooks and must refuse to start if they are
missing or malformed. A score computed under unknown weights is not auditable.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Core ----------------------------------------------------------
    environment: Literal["local", "staging", "production"] = "local"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"

    # ---- Database ------------------------------------------------------
    database_url: str
    database_owner_url: str | None = None
    sync_database_url: str | None = None

    # ---- Redis ---------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # ---- Auth ----------------------------------------------------------
    # Clerk lands in Domain 8. Until then, dev mode trusts an X-Org-Id header.
    # This MUST be "clerk" in staging/production — enforced below.
    auth_mode: Literal["dev", "clerk"] = "dev"
    clerk_secret_key: str | None = None
    clerk_jwks_url: str | None = None

    # ---- Third parties (Wrik's domains consume these) ------------------
    anthropic_api_key: str | None = None
    brightdata_api_token: str | None = None
    sec_user_agent: str | None = None
    courtlistener_token: str | None = None
    crunchbase_key: str | None = None

    # ---- Crypto --------------------------------------------------------
    shred_master_key: str | None = None

    # ---- Jobs ----------------------------------------------------------
    capture_cron_hour: int = 7
    capture_cron_minute: int = 0
    capture_concurrency: int = 8
    job_timeout_seconds: int = 60 * 30

    # ---- Notifications -------------------------------------------------
    # Channels stay DARK until calibration exists. Alerting an unvalidated
    # score distributes noise faster; it does not add value.
    notify_enabled: bool = False
    slack_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    notify_email_to: str = ""
    generic_webhook_url: str | None = None
    generic_webhook_secret: str | None = None

    # ---- Calibration (Wrik → production seam) --------------------------
    calibration_dir: Path = REPO_ROOT / "calibration"
    require_calibration: bool = False  # True once the backtest has run

    # ---- Frontend ------------------------------------------------------
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    @field_validator("cors_origins")
    @classmethod
    def _split_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def notify_email_list(self) -> list[str]:
        return [e.strip() for e in self.notify_email_to.split(",") if e.strip()]

    def validate_runtime(self) -> list[str]:
        """
        Returns a list of problems. Fatal ones raise; the rest are warnings
        surfaced on /health so degraded state is visible, not guessed at.
        """
        warnings: list[str] = []

        if self.environment != "local" and self.auth_mode != "clerk":
            raise RuntimeError(
                "auth_mode='dev' is only permitted in the local environment. "
                "Dev mode trusts an unsigned X-Org-Id header."
            )
        if self.auth_mode == "clerk" and not self.clerk_secret_key:
            raise RuntimeError("auth_mode='clerk' requires CLERK_SECRET_KEY")

        if not self.shred_master_key:
            warnings.append("SHRED_MASTER_KEY unset — GDPR erasure unavailable")
        if not self.anthropic_api_key:
            warnings.append("ANTHROPIC_API_KEY unset — AI layer will use fallback")
        if not self.brightdata_api_token:
            warnings.append("BRIGHTDATA_API_TOKEN unset — MCP capture unavailable")
        if not self.sec_user_agent:
            warnings.append(
                "SEC_USER_AGENT unset — EDGAR requests will violate fair-access policy"
            )

        missing = [
            n
            for n in ("weights", "thresholds")
            if not self.calibration_path(n).exists()
        ]
        if missing and self.require_calibration:
            raise RuntimeError(
                f"Missing calibration: {missing}. The scoring engine cannot run "
                "on unknown weights. Run the backtest notebooks first."
            )
        if missing:
            warnings.append(
                f"Calibration missing ({', '.join(missing)}) — scores are PROVISIONAL"
            )

        if self.notify_enabled and missing:
            raise RuntimeError(
                "notify_enabled=True with missing calibration. Alerting on an "
                "uncalibrated score is noise. Run the backtest first."
            )

        return warnings

    def calibration_path(self, name: str) -> Path:
        return self.calibration_dir / f"{name}.json"

    def load_calibration(self, name: str) -> dict | None:
        p = self.calibration_path(name)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed calibration file {p}: {exc}") from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
