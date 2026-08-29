from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """環境変数と `backend/.env` から読む設定。

    `.env` と既定の DB は backend からの絶対パスで解決する。相対パスにすると
    起動時の CWD で読む先が変わり、リポジトリルートから起動する uvicorn と
    `--directory backend` で走る pytest が別のファイルを見てしまう。
    """

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="APP_")

    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'chat.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
