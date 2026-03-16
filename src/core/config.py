from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Meta Threads
    threads_app_id: str = ""
    threads_app_secret: str = ""
    threads_access_token: str = ""
    threads_user_id: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://aiai:aiai_secret@localhost:5432/aiai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Posting
    default_post_language: str = "ja"
    max_post_length: int = 500

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
