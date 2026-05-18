from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    bot_username: str | None = Field(default=None, alias="BOT_USERNAME")
    database_url: str = Field(alias="DATABASE_URL")
    bot_storage_path: Path = Field(default=Path("./data"), alias="BOT_STORAGE_PATH")
    healthcheck_host: str = Field(default="0.0.0.0", alias="HEALTHCHECK_HOST")
    healthcheck_port: int = Field(default=8080, alias="PORT")
    feedback_chat_id: int | None = Field(default=None, alias="FEEDBACK_CHAT_ID")
    dashboard_token: str | None = Field(default=None, alias="DASHBOARD_TOKEN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.bot_storage_path.mkdir(parents=True, exist_ok=True)
    return settings
