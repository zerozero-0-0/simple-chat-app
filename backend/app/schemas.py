from pydantic import BaseModel, ConfigDict, Field

# 名前の上限。実際に弾いているのはここだけで、`models.py` の `String(32)` は
# SQLite が VARCHAR の長さを見ないため事実上ドキュメント。
NAME_MAX_LENGTH = 32

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
