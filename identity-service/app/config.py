from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Prequal Identity Service"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "identity_service"
    POSTGRES_PORT: str = "5432"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"

    SESSION_EXPIRY_SECONDS: int = 900

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if os.getenv("DATABASE_URL"):
            return
        if not self.POSTGRES_PASSWORD:
            raise ValueError("POSTGRES_PASSWORD environment variable must be set")

    @property
    def DATABASE_URL(self) -> str:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            return redis_url
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        case_sensitive = True


settings = Settings()