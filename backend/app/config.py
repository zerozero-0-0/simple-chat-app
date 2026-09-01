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

    # 通信を許すオリジン。公開するときはここに本番のオリジンを並べる
    cors_origins: list[str] = []

    # 手元のどのポートからでも通す。`next dev` は 3000 が埋まっていれば 3001 で
    # 上がるので、ポートを 1 つに決め打つとその場で全部 CORS に弾かれる。
    # 公開するときは空にして、cors_origins だけで許す
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1|\[::1\]):\d+"

    # セッションの猶予。残りが半分を切ると延びるので、最後に使ってから
    # 最短でこの半分は保つ
    session_ttl_hours: int = 24 * 14  # 14日間
    session_cookie_secure: bool = False


settings = Settings()
