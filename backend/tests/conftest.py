from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import Room


@pytest.fixture(autouse=True)
def plain_session_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    """外の `APP_SESSION_COOKIE_SECURE` からスイート全体を隔離する。"""
    monkeypatch.setattr(settings, "session_cookie_secure", False)


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


@pytest.fixture
async def other_device(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """同じサーバーに繋ぐ 2 台目の端末。Cookie は `client` と別に持つ。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        yield other


@pytest.fixture
async def room(session: AsyncSession) -> Room:
    """共通の部屋。本番では lifespan が用意する。"""
    room = Room(name="みんなの部屋")
    session.add(room)
    await session.commit()
    return room
