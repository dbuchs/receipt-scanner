from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "receipt-scanner"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"

    # Encryption key for YNAB tokens (Fernet base64url-encoded 32-byte key)
    ENCRYPTION_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql://receipt:receipt@localhost:5432/receipt_scanner"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "receipts"

    # YNAB OAuth
    YNAB_CLIENT_ID: str = ""
    YNAB_CLIENT_SECRET: str = ""
    YNAB_REDIRECT_URI: str = "http://localhost:8000/ynab/callback"

    # Watched folder
    WATCHED_FOLDER_PATH: str = "/data/watched"
    WATCHED_FOLDER_POLL_SECONDS: int = 30

    # ML model storage
    MODEL_DIR: str = "/data/models"


@lru_cache
def get_settings() -> Settings:
    return Settings()
