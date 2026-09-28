"""Application settings, loaded from environment variables and the `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT_DIR / "data" / "snapshots"
MANUAL_DIR = ROOT_DIR / "data" / "manual"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # Safety switches (see CLAUDE.md). Dry-run stays on until Jonas turns it off on purpose.
    dry_run: bool = True
    auto_lineup: bool = False

    # Web server
    host: str = "127.0.0.1"
    port: int = 8000
    open_browser: bool = True

    # Local state (SQLite database, HTTP cache)
    data_dir: Path = ROOT_DIR / "var"

    # Anthropic (optional). Without a key, all texts come from templates.
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-5"
    ai_daily_budget_usd: float = 0.50

    # Yahoo (phase 2)
    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_redirect_uri: str = "https://localhost:8000/auth/callback"
    yahoo_league_id: str = ""

    @property
    def db_path(self) -> Path:
        return self.data_dir / "fantasy.sqlite"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    return settings
