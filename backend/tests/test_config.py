from pathlib import Path

import pytest

from app.config import BACKEND_DIR, Settings

SQLITE_PREFIX = "sqlite+aiosqlite:///"


def test_env_file_in_cwd_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CWD に置かれた `.env` を読まないこと。

    リポジトリルートから起動する uvicorn と `--directory backend` で走る pytest が、
    同じ `backend/.env` を読む必要がある。
    """
    cwd_database_url = f"{SQLITE_PREFIX}./cwd.db"
    (tmp_path / ".env").write_text(f"APP_DATABASE_URL={cwd_database_url}\n")
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    assert Settings().database_url != cwd_database_url


def test_default_database_lives_in_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """既定の DB が backend の下の絶対パスに解決されること。

    相対パスだと起動した場所ごとに別の DB ができる。`.env` の内容に左右されない
    よう、既定値だけを見る。
    """
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)

    database_url = Settings(_env_file=None).database_url

    path = Path(database_url.removeprefix(SQLITE_PREFIX))
    assert path.is_absolute()
    assert path.parent == BACKEND_DIR


def test_production_marks_the_session_cookie_secure() -> None:
    """本番では設定を足さなくても HTTPS でしか Cookie を送らせないこと。"""
    assert Settings(_env_file=None, environment="production").session_cookie_secure


def test_development_leaves_the_session_cookie_usable_over_http() -> None:
    """ローカルは http なので、有効にするとブラウザが Cookie を捨てる。"""
    assert not Settings(_env_file=None, environment="development").session_cookie_secure


def test_environment_defaults_to_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)

    assert Settings(_env_file=None).environment == "development"
