"""Settings loaded from environment variables / .env - never hardcode
secrets here. In production (Railway) these are set as service Variables,
exactly like the other bots in this family.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    bot_token: str
    allowed_user_ids: str  # comma-separated numeric Telegram user ids of operators/admins

    # Database - default points at a Railway persistent volume mount (/data).
    # A plain "./start_message_bot.db" works locally but MUST NOT be used in
    # production - Railway containers have an ephemeral filesystem, so
    # anything not on an attached volume is wiped on every redeploy.
    database_url: str = "sqlite+aiosqlite:////data/start_message_bot.db"

    @property
    def allowed_user_id_set(self) -> set[int]:
        return {int(x.strip()) for x in self.allowed_user_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
