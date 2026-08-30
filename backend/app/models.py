from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    """SQLite はタイムゾーンを保持しないので、UTC の naive datetime で揃える。"""
    return datetime.now(UTC).replace(tzinfo=None)


def new_public_id() -> str:
    return uuid4().hex


class User(Base):
    """`id` は FK と索引に使う内部用。API と URL には `public_id` だけを出す。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, default=new_public_id
    )
    login_name: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["RoomMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """Cookie で渡すセッション。`token_hash` は Cookie の値の SHA-256。"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="sessions")


class Room(Base):
    """`id` は FK と索引に使う内部用。API と URL には `public_id` だけを出す。"""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, default=new_public_id
    )
    name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list["RoomMember"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )


class RoomMember(Base):
    """誰がどの部屋にいるか。既読は `last_read_message_id` の watermark で持つ。"""

    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    last_read_message_id: Mapped[int | None] = mapped_column(default=None)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    room: Mapped[Room] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Message(Base):
    """連番の `id` をそのまま公開し、`?after=<id>` のカーソルに使う。

    `client_message_id` はクライアントが採番する。再送されても
    `UNIQUE(room_id, sender_id, client_message_id)` で 2 通にならない。
    送信者を含めるので、別のユーザーが同じ値を採番しても衝突しない。
    """

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("room_id", "sender_id", "client_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    client_message_id: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    room: Mapped[Room] = relationship()
    sender: Mapped[User] = relationship()
