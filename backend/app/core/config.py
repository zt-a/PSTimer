from functools import cached_property, lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment (.env). No hardcoded secrets."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "PlayStation Club"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://pstimer:pstimer@localhost:5432/pstimer"
    )

    # Security
    JWT_SECRET: str = ""  # generated below if empty (for dev), must be >32 chars
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours

    # Analytics / history
    CLUB_TIMEZONE: str = "Asia/Bishkek"  # local timezone used for day boundaries
    HISTORY_RETENTION_DAYS: int = 30  # completed sessions older than this are purged
    CLEANUP_INTERVAL_HOURS: int = 6  # how often the retention worker runs

    # Telegram bot (optional). When TELEGRAM_BOT_TOKEN is empty the bot is
    # disabled entirely. Subscription is open: anyone who sends /start gets
    # notifications and can view stations.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_POLL_INTERVAL: int = 15  # seconds between dashboard event checks
    TELEGRAM_UPDATE_TIMEOUT: int = 25  # long-poll timeout for getUpdates

    # CORS
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://localhost:5174,http://localhost:4173"
    )

    # Bootstrap admin (only used when no admin exists yet)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"  # MUST be changed in production

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN.strip())

    @cached_property
    def jwt_secret(self) -> str:
        """Return a usable JWT secret.

        If JWT_SECRET is set (>=32 chars) it is used. Otherwise a random
        secret is generated once and persisted, so it survives restarts:

        * in Docker: on the ``backendsecrets`` volume at ``/app/.secrets``;
        * locally: in ``backend/.jwt_secret``.

        Without persistence every restart would invalidate all issued tokens.
        Set JWT_SECRET explicitly for multi-instance setups.
        """
        import logging
        import os
        from pathlib import Path

        secret = self.JWT_SECRET.strip()
        if len(secret) >= 32:
            return secret

        path = self._jwt_secret_path()
        try:
            existing = path.read_text().strip()
            if len(existing) >= 32:
                return existing
        except FileNotFoundError:
            pass

        generated = os.urandom(32).hex()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(generated)
            os.chmod(path, 0o600)
        except OSError:
            pass
        logging.getLogger("app").warning(
            "JWT_SECRET is not set — generating a persisted secret at %s. "
            "For multi-instance deployments set JWT_SECRET in .env.",
            path,
        )
        return generated

    @staticmethod
    def _jwt_secret_path():
        """Prefer the mounted Docker secrets volume, else the app root dir."""
        from pathlib import Path

        docker_secrets = Path("/app/.secrets/.jwt_secret")
        if docker_secrets.parent.is_dir():
            return docker_secrets
        return Path(__file__).resolve().parents[2] / ".jwt_secret"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
