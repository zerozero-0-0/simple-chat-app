from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import models  # noqa: F401  # create_all の前にテーブルを登録する
from app.config import settings
from app.db import Base, engine, session_factory
from app.models import Room
from app.routers import auth, health, messages, rooms

DEFAULT_ROOM_NAME = "みんなの部屋"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 全員が入る共通の部屋を 1 つ用意する
    async with session_factory() as db:
        if await db.scalar(select(Room).limit(1)) is None:
            db.add(Room(name=DEFAULT_ROOM_NAME))
            await db.commit()

    yield
    await engine.dispose()


app = FastAPI(title="simple-chat-app", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
