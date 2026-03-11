"""Application configuration via Pydantic Settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "phoenix_dev"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Scraper
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    scrape_max_retries: int = 3
    scrape_max_profiles: int = 50

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Notifications
    notification_url: str = "http://localhost:8888/notify"


settings = Settings()
