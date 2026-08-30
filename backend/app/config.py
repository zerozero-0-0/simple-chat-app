from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """環境変数と `backend/.env` から読む設定。

    `.env` と既定の DB は backend からの絶対パスで解決するので、どこから
    起動しても同じものを見る。
    """

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="APP_")

    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'chat.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:3000"]

    session_ttl_hours: int = 24 * 14  # 14日間
    session_cookie_secure: bool = False


settings = Settings()
