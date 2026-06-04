"""
Application Configuration — Ollama (local) edition
All settings loaded from environment variables / .env file.
"""

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    APP_NAME: str = "AI Prescription Explainer & Safety Assistant (Ollama)"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Security ───────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "*"]

    # ── Ollama ─────────────────────────────────────────────────────────────
    # Base URL of your Ollama server (default: local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Model to use — recommended options (best → lightest):
    #   llama3.1:8b       — best JSON reliability, needs ~8 GB RAM
    #   llama3.2:3b       — good, needs ~4 GB RAM
    #   mistral:7b        — excellent at structured output
    #   phi3:mini         — very fast, needs ~2.5 GB RAM
    #   gemma2:2b         — fast, low RAM, decent JSON
    OLLAMA_MODEL: str = "llama3.2:3b"

    # Generation parameters
    OLLAMA_TEMPERATURE: float = 0.1    # low = deterministic/factual
    OLLAMA_NUM_PREDICT: int = 2048     # max tokens to generate
    OLLAMA_TOP_P: float = 0.9
    OLLAMA_REPEAT_PENALTY: float = 1.1

    # How long to wait for a response (seconds) — local models can be slow
    OLLAMA_TIMEOUT: int = 120

    # ── Tesseract OCR ──────────────────────────────────────────────────────
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    TESSERACT_LANG: str = "eng"
    OCR_DPI: int = 300
    OCR_SUPPORTED_EXTENSIONS: List[str] = [
        ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"
    ]

    # ── File Upload ────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # ── Multilingual ──────────────────────────────────────────────────────
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: List[str] = ["en", "ta", "hi", "fr", "es", "de", "zh", "ar"]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def upload_dir_path(self) -> str:
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        return self.UPLOAD_DIR


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
