"""Environment configuration. Values come from the process environment or backend/.env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_publishable_key: str = ""
    # Used only by db.service_client() for server-owned tables; never for user-scoped reads.
    supabase_secret_key: str = ""
    allowed_origins: str = "http://localhost:5173"
    # Skill extraction (docs/skill-intelligence.md §10). Unset key -> those endpoints answer 503.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    request_timeout_seconds: float = 10.0

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
