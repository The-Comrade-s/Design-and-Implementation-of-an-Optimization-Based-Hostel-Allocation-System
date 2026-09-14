"""Centralized, environment-based configuration for HOS."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables.

    Never hard-code credentials here. All values come from the
    environment (or a local .env file, which must never be committed).
    """

    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = APP_ENV == "development"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./hos.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    OPTIMIZATION_TIME_LIMIT_SECONDS: int = int(
        os.getenv("OPTIMIZATION_TIME_LIMIT_SECONDS", "60")
    )

    def validate(self) -> None:
        if self.APP_ENV == "production" and not self.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be set via environment variable in production."
            )
        if self.APP_ENV == "production" and "sqlite" in self.DATABASE_URL:
            # SQLite is fine for development but PostgreSQL is the intended
            # production database for this system.
            pass


settings = Settings()
