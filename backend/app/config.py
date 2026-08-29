from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """環境変数と `backend/.env` から読む設定。

    `.env` と既定の DB は backend からの絶対パスで解決する。相対パスにすると
    起動時の CWD で読む先が変わり、リポジトリルートから起動する uvicorn と
    `--directory backend` で走る pytest が別のファイルを見てしまう。
    """

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="APP_")

    environment: Literal["development", "production"] = "development"

    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'chat.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:3000"]

    session_ttl_hours: int = 24 * 14

    @property
    def session_cookie_secure(self) -> bool:
        """本番では HTTPS でしか Cookie を送らせない。

        設定を足し忘れると平文で飛ぶ、という向きの間違いをしないよう
        `environment` から導出する。ローカルは http なので無効にしないと、
        サーバーは 200 を返すのにブラウザが Cookie を捨てる。
        """
        return self.environment == "production"


settings = Settings()
