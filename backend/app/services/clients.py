from functools import lru_cache

from openai import OpenAI
from supabase import Client, create_client

from app.core.config import get_settings, require_setting


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=require_setting(settings.openai_api_key, "OPENAI_API_KEY"))


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(
        require_setting(settings.supabase_url, "SUPABASE_URL"),
        require_setting(settings.supabase_service_role_key, "SUPABASE_SERVICE_ROLE_KEY"),
    )
