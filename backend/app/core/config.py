from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Shoe Matcher API"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shoematcher"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/shoematcher"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Auth
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # AI
    ANTHROPIC_API_KEY: Optional[str] = None
    REPLICATE_API_TOKEN: Optional[str] = None
    REPLICATE_MODEL: str = "ibm-granite/granite-4.0-h-small"
    LLM_PROVIDER: str = "none"

    # Affiliate
    AMAZON_AFFILIATE_TAG: Optional[str] = None
    RUNNING_WAREHOUSE_AFFILIATE_ID: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "https://shoematcher.com"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
