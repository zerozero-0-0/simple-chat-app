from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import SESSION_COOKIE_NAME, hash_token
from app.models import Session, User, utcnow


async def signup(client: AsyncClient, login_name: str = "alice", **extra: str) -> None:
    response = await client.post(
        "/api/auth/signup", json={"login_name": login_name, **extra}
    )
    assert response.status_code == 201


async def test_signup_returns_user_and_starts_session(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "alice"})

    assert response.status_code == 201
    body = response.json()
    assert body["login_name"] == "alice"
    assert body["public_id"]

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == body


async def test_signup_defaults_display_name_to_login_name(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "alice"})

    assert response.json()["display_name"] == "alice"


async def test_signup_keeps_given_display_name(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/signup", json={"login_name": "alice", "display_name": "アリス"}
    )

    assert response.json()["display_name"] == "アリス"


async def test_signup_rejects_duplicate_login_name(client: AsyncClient) -> None:
    await signup(client)

    response = await client.post("/api/auth/signup", json={"login_name": "alice"})

    assert response.status_code == 409


async def test_display_name_may_be_shared(client: AsyncClient) -> None:
    await signup(client, "alice", display_name="ちゃん")

    response = await client.post(
        "/api/auth/signup", json={"login_name": "bob", "display_name": "ちゃん"}
    )

    assert response.status_code == 201


async def test_login_starts_session_for_existing_user(client: AsyncClient) -> None:
    await signup(client)
    await client.post("/api/auth/logout")

    response = await client.post("/api/auth/login", json={"login_name": "alice"})

    assert response.status_code == 200
    assert response.json()["login_name"] == "alice"
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_login_rejects_unknown_user(client: AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"login_name": "nobody"})

    assert response.status_code == 404


async def test_session_cookie_is_http_only(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "alice"})

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


async def test_cookie_value_is_not_stored(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DB に入るのはハッシュだけ。Cookie の値がそのまま残っていないこと。"""
    await signup(client)
    token = client.cookies[SESSION_COOKIE_NAME]

    stored = (await session.scalars(select(Session))).all()

    assert [row.token_hash for row in stored] == [hash_token(token)]


async def test_me_rejects_missing_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_rejects_unknown_cookie(client: AsyncClient) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-token")

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_rejects_expired_session(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signup(client)
    stored = await session.scalar(select(Session))
    assert stored is not None
    stored.expires_at = utcnow() - timedelta(seconds=1)
    await session.commit()

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_expired_session_is_removed(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signup(client)
    stored = await session.scalar(select(Session))
    assert stored is not None
    stored.expires_at = utcnow() - timedelta(seconds=1)
    await session.commit()

    await client.get("/api/auth/me")

    assert (await session.scalars(select(Session))).all() == []


async def test_logout_ends_the_session(client: AsyncClient) -> None:
    await signup(client)

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_logout_without_session_succeeds(client: AsyncClient) -> None:
    response = await client.post("/api/auth/logout")

    assert response.status_code == 204


async def test_logout_leaves_other_sessions_alone(
    client: AsyncClient, session: AsyncSession
) -> None:
    """別の端末のセッションまで切らないこと。

    2 回目のログインで Cookie が入れ替わるので、logout が切るのは 2 本目だけ。
    1 本目は別の端末に残っているものとして扱う。
    """
    await signup(client)
    first_token = client.cookies[SESSION_COOKIE_NAME]
    await client.post("/api/auth/login", json={"login_name": "alice"})
    assert client.cookies[SESSION_COOKIE_NAME] != first_token

    await client.post("/api/auth/logout")

    remaining = (await session.scalars(select(Session))).all()
    assert [row.token_hash for row in remaining] == [hash_token(first_token)]


async def test_login_name_must_be_usable_in_a_url(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "a b/c"})

    assert response.status_code == 422


async def test_public_id_differs_from_internal_id(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signup(client)

    user = await session.scalar(select(User))

    assert user is not None
    assert user.public_id != str(user.id)
