from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app


@pytest.fixture(autouse=True)
def development_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """外の `APP_ENVIRONMENT` にスイート全体が左右されないようにする。

    本番相当の設定を入れたシェルで走らせると、Cookie に `Secure` が付いて
    `http://test` 越しの httpx が Cookie を保持しなくなり、認証まわりが軒並み落ちる。
    """
    monkeypatch.setattr(settings, "environment", "development")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """テストごとに使い捨てのインメモリ DB を用意する。

    StaticPool で単一コネクションを共有しないと、接続のたびに別の
    インメモリ DB が作られてテーブルが見えなくなる。
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
