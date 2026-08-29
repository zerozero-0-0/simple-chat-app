"""セッションの発行・破棄と、リクエストからの現在ユーザーの取り出し。"""

import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import get_session
from app.models import Session, User, utcnow

SESSION_COOKIE_NAME = "session_id"

DbSession = Annotated[AsyncSession, Depends(get_session)]
SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_session(db: AsyncSession, user: User, response: Response) -> None:
    """セッションを作り、Cookie に載せる。Cookie に入るのは DB に無い生の値。"""
    token = secrets.token_urlsafe(32)
    ttl = timedelta(hours=settings.session_ttl_hours)
    db.add(
        Session(
            token_hash=hash_token(token), user_id=user.id, expires_at=utcnow() + ttl
        )
    )
    await db.commit()

    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


async def revoke_session(
    db: AsyncSession, token: str | None, response: Response
) -> None:
    """Cookie が無効でも Cookie は消す。ログアウトは何度呼んでも同じ結果にする。"""
    if token is not None:
        await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
        await db.commit()

    response.delete_cookie(SESSION_COOKIE_NAME)


async def get_current_user(db: DbSession, session_id: SessionCookie = None) -> User:
    if session_id is None:
        raise _unauthenticated()

    session = await db.scalar(
        select(Session)
        .where(Session.token_hash == hash_token(session_id))
        .options(selectinload(Session.user))
    )
    if session is None:
        raise _unauthenticated()

    if session.expires_at <= utcnow():
        await db.delete(session)
        await db.commit()
        raise _unauthenticated()

    return session.user


def _unauthenticated() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "ログインしてください")


CurrentUser = Annotated[User, Depends(get_current_user)]
