"""DukaanAI backend configuration module."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core App
    APP_NAME: str = "DukaanAI"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    APP_SECRET_KEY: str = Field(
        default="development-insecure-secret-key-change-in-production-min32chars",
        description="Application secret key for signing tokens / sessions",
    )

    # Server binding
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/dukaanai"

    # Localization
    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    # Ingestion / Upload limits
    MAX_UPLOAD_MB: int = 20

    @property
    def cors_origins(self) -> list[str]:
        """Compute list of all allowed origins including FRONTEND_ORIGIN."""
        origins = set(self.ALLOWED_ORIGINS)
        if self.FRONTEND_ORIGIN:
            origins.add(self.FRONTEND_ORIGIN.rstrip("/"))
        return list(origins)


@lru_cache
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()
