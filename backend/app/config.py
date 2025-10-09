"""Application configuration using pydantic settings."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "ScannerForge"
    postgres_dsn: str = "postgresql+asyncpg://scannerforge:scannerforge@db:5432/scannerforge"
    redis_url: str = "redis://redis:6379/0"
    allowed_origins: list[str] = ["http://localhost:5173"]
    recording_dir: str = "/data/recordings"
    default_stream_plugin: str = "broadcastify"

    class Config:
        env_prefix = "SCANNERFORGE_"
        env_file = ".env"


settings = Settings()
