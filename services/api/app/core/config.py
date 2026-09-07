from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    database_url: str = ''
    supabase_url: str = Field(default='', validation_alias=AliasChoices('SUPABASE_URL', 'SUPABASE_PROJECT_URL'))
    supabase_anon_key: str = Field(default='', validation_alias=AliasChoices('SUPABASE_ANON_KEY', 'anon_public_key'))
    portal_demo_mode: bool = False
    portal_demo_database: str = str(REPO_ROOT / '.local' / 'staff-demo.sqlite3')
    staff_portal_origins: str = 'http://localhost:5174,http://127.0.0.1:5174'
    staff_generation_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
