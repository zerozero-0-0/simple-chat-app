import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer


def as_utc(value: datetime) -> str:
    """DB の naive な値を UTC として、オフセット付きで書き出す。

    オフセットが無い文字列は、ブラウザがローカル時刻として読む。
    """
    return value.replace(tzinfo=UTC).isoformat()


UtcDatetime = Annotated[datetime, PlainSerializer(as_utc)]

NAME_MAX_LENGTH = 32
MESSAGE_BODY_MAX_LENGTH = 1000
CLIENT_MESSAGE_ID_MAX_LENGTH = 64


def cleaned(value: Any) -> Any:
    """前後の空白を落とし、NFC に揃える。

    `login_name` は認証の鍵なので、見た目が同じ名前は同じユーザーになる必要がある。
    NFD の「が」(か + 濁点) は NFC の「が」と同じ 1 人として扱う。
    """
    if not isinstance(value, str):
        return value
    return unicodedata.normalize("NFC", value).strip()


# 上限は Unicode のコードポイント単位。フロントも `[...value].length` で数える。
# 長さは空白を落とした後の値で見る
Name = Annotated[
    str,
    BeforeValidator(cleaned),
    Field(min_length=1, max_length=NAME_MAX_LENGTH),
]


class SignupRequest(BaseModel):
    login_name: Name
    display_name: Name | None = None


class LoginRequest(BaseModel):
    login_name: Name


class UserResponse(BaseModel):
    """本人に返す表現。他のユーザーには `login_name` を出さない。"""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    login_name: str
    display_name: str


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    name: str


def trimmed(value: Any) -> Any:
    """前後の空白を落とす。"""
    if not isinstance(value, str):
        return value
    return value.strip()


# 前後の空白だけ落として中身はそのまま残す。長さは落とした後の値で見る
Body = Annotated[
    str,
    BeforeValidator(trimmed),
    Field(min_length=1, max_length=MESSAGE_BODY_MAX_LENGTH),
]


class MessageCreateRequest(BaseModel):
    client_message_id: str = Field(
        min_length=1, max_length=CLIENT_MESSAGE_ID_MAX_LENGTH
    )
    body: Body


class MessageSender(BaseModel):
    """他のユーザーにも見える表現。`login_name` は出さない。"""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    display_name: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_message_id: str
    body: str
    created_at: UtcDatetime
    sender: MessageSender
