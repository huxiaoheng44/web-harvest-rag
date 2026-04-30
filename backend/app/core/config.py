from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    frontend_origin: str = "http://localhost:3000"
    match_count: int = 6
    min_similarity: float = 0.35

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def require_setting(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value
