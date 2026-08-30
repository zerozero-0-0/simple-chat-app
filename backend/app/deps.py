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
from app.models import Room, RoomMember, Session, User, utcnow
from app.stream import stream

SESSION_COOKIE_NAME = "session_id"

# 期限までの残りがこの割合を切ったら DB を書き換える。毎回書き込むと、
# 読むだけのリクエストでも DB に書くことになる
REFRESH_AT = 0.5

DbSession = Annotated[AsyncSession, Depends(get_session)]
SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_ttl() -> timedelta:
    return timedelta(hours=settings.session_ttl_hours)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(session_ttl().total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


async def issue_session(db: AsyncSession, user: User, response: Response) -> None:
    """セッションを作り、Cookie に載せる。Cookie に入るのは DB に無い生の値。"""
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + session_ttl(),
        )
    )
    await db.commit()

    set_session_cookie(response, token)


async def revoke_session(
    db: AsyncSession, token: str | None, response: Response
) -> None:
    """セッションを消して Cookie を落とす。何度呼んでも同じ結果になる。"""
    if token is not None:
        await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
        await db.commit()
        # WebSocket はセッションを接続時にしか見ない。ここで切る
        await stream.close_session(hash_token(token))

    response.delete_cookie(SESSION_COOKIE_NAME)


async def find_session_user(db: AsyncSession, token: str) -> User | None:
    """Cookie の値からユーザーを引く。期限切れのセッションは消して None を返す。

    WebSocket からも使う。Cookie の貼り直しは HTTP のリクエストに任せる。
    """
    session = await db.scalar(
        select(Session)
        .where(Session.token_hash == hash_token(token))
        .options(selectinload(Session.user))
    )
    if session is None:
        return None

    if session.expires_at <= utcnow():
        await db.delete(session)
        await db.commit()
        return None

    await _extend(db, session)
    return session.user


async def get_current_user(
    db: DbSession, response: Response, session_id: SessionCookie = None
) -> User:
    if session_id is None:
        raise _unauthenticated()

    user = await find_session_user(db, session_id)
    if user is None:
        raise _unauthenticated()

    # エラー応答では依存関係が載せた Set-Cookie が捨てられる。延長したときだけ
    # 貼り直すと、DB と Cookie の期限がずれたまま戻らなくなる
    set_session_cookie(response, session_id)
    return user


async def _extend(db: AsyncSession, session: Session) -> None:
    """使われている限り期限を先に延ばす。

    残りが半分を切ったときだけ書き戻すので、最後に使ってから TTL の半分から
    TTL までの間に切れる。
    """
    ttl = session_ttl()
    if session.expires_at - utcnow() > ttl * REFRESH_AT:
        return

    session.expires_at = utcnow() + ttl
    await db.commit()


def _unauthenticated() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "ログインしてください")


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_member_room(public_id: str, user: CurrentUser, db: DbSession) -> Room:
    """URL が指す部屋を返す。入室していなければ弾く。"""
    room = await db.scalar(select(Room).where(Room.public_id == public_id))
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "その部屋はありません")

    member = await db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id, RoomMember.user_id == user.id
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "この部屋に入っていません")

    return room


MemberRoom = Annotated[Room, Depends(get_member_room)]
