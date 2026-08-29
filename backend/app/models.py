from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    """SQLite はタイムゾーンを保持しないので、UTC の naive datetime で揃える。

    aware な値を書くと読み出しで tzinfo が落ち、比較のたびに naive と aware が
    混ざる。書く側で UTC に寄せておけば、DB を経由しても意味が変わらない。
    """
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


class Session(Base):
    """Cookie で渡すセッション。

    DB に置くのは Cookie の値そのものではなく、その SHA-256。DB が漏れても
    そのままセッションを乗っ取れないようにするため。
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="sessions")
