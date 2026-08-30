from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def as_utc(value: datetime) -> str:
    """DB の naive な値を UTC として、オフセット付きで書き出す。

    オフセットが無い文字列は、ブラウザがローカル時刻として読む。
    """
    return value.replace(tzinfo=UTC).isoformat()


UtcDatetime = Annotated[datetime, PlainSerializer(as_utc)]

NAME_MAX_LENGTH = 32
MESSAGE_BODY_MAX_LENGTH = 1000
CLIENT_MESSAGE_ID_MAX_LENGTH = 64

LOGIN_NAME = Field(
    min_length=1, max_length=NAME_MAX_LENGTH, pattern=r"^[A-Za-z0-9_-]+$"
)
DISPLAY_NAME = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)


class SignupRequest(BaseModel):
    login_name: str = LOGIN_NAME
    display_name: str | None = DISPLAY_NAME


class LoginRequest(BaseModel):
    login_name: str = LOGIN_NAME


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


class MessageCreateRequest(BaseModel):
    client_message_id: str = Field(
        min_length=1, max_length=CLIENT_MESSAGE_ID_MAX_LENGTH
    )
    body: str = Field(min_length=1, max_length=MESSAGE_BODY_MAX_LENGTH)


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
