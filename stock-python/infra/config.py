"""
Application configuration.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Project
    PROJECT_NAME: str = "Stock API"
    DEBUG: bool = True
    VERSION: str = "1.0.0"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/stock"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Email (Resend)
    RESEND_API_KEY: str = ""

    # Email (AWS SES)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # Email settings
    EMAIL_FROM: str = "StockPy <noreply@stockpy.com>"
    EMAIL_FROM_NAME: str = "StockPy"

    # WebPush (VAPID keys)
    WEB_PUSH_PUBLIC_KEY: str = ""
    WEB_PUSH_PRIVATE_KEY: str = ""
    WEB_PUSH_SUBJECT: str = "mailto:admin@stockpy.com"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()