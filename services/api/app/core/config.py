from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_anon_key: str

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()