from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import (
    CurrentUser,
    DbSession,
    SessionCookie,
    issue_session,
    revoke_session,
)
from app.models import User
from app.schemas import LoginRequest, SignupRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest, response: Response, db: DbSession
) -> UserResponse:
    user = User(
        login_name=payload.login_name,
        display_name=payload.display_name or payload.login_name,
    )
    db.add(user)
    try:
        # 事前に検索せず一意制約に任せる。検索してから挿入すると、その間に
        # 同じ名前が入りうる
        await db.flush()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "この名前は既に使われています"
        ) from error

    await issue_session(db, user, response)
    return UserResponse.model_validate(user)


@router.post("/login")
async def login(
    payload: LoginRequest, response: Response, db: DbSession
) -> UserResponse:
    user = await db.scalar(select(User).where(User.login_name == payload.login_name))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "この名前のユーザーはいません")

    await issue_session(db, user, response)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, db: DbSession, session_id: SessionCookie = None
) -> None:
    await revoke_session(db, session_id, response)


@router.get("/me")
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
