from pydantic import BaseModel, ConfigDict, Field

LOGIN_NAME = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
DISPLAY_NAME = Field(min_length=1, max_length=32)


class SignupRequest(BaseModel):
    login_name: str = LOGIN_NAME
    display_name: str | None = Field(default=None, min_length=1, max_length=32)


class LoginRequest(BaseModel):
    login_name: str = LOGIN_NAME


class UserResponse(BaseModel):
    """本人に返す表現。他のユーザーには `login_name` を出さない。"""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    login_name: str
    display_name: str
