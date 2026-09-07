from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# Resolve .env robustly: check backend/ first, then project root — regardless of CWD
_BASE_DIR = Path(__file__).resolve().parent.parent.parent      # backend/
_PROJECT_ROOT = _BASE_DIR.parent                                # Rabta AI/


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    SECRET_KEY: str = "development_secret_key"

    # WhatsApp Cloud API
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: str = "rabta_webhook_verify_token_12345"
    WHATSAPP_APP_SECRET: Optional[str] = None

    # Google Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.7-flash"

    # Deepgram Voice
    DEEPGRAM_API_KEY: Optional[str] = None

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://postgres:changeme@localhost:5432/rabta_dev"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Production domain and CORS
    DOMAIN: Optional[str] = None                  # e.g. api.yourdomain.com
    ALLOWED_ORIGINS: Optional[str] = None          # e.g. https://yourdomain.com

    # Embeddings backend: 'postgres_jsonb' (default) or 'pgvector' (requires extension installed)
    EMBEDDINGS_BACKEND: str = "postgres_jsonb"
    # Qdrant removed — consolidated into Postgres to eliminate separate vector DB operational overhead

    # Visual Search — Gemini Embedding 2
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-002"
    GEMINI_EMBEDDING_DIM: int = 1536  # Matryoshka-truncated from 3072

    # Visual Search — Confidence thresholds (cosine similarity)
    VISUAL_MATCH_HIGH_THRESHOLD: float = 0.82
    VISUAL_MATCH_MEDIUM_THRESHOLD: float = 0.65
    VISUAL_MATCH_LOW_THRESHOLD: float = 0.50

    model_config = SettingsConfigDict(
        env_file=(str(_BASE_DIR / ".env"), str(_PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
