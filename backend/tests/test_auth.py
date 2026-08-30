from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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


async def test_session_cookie_is_not_secure_over_http(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "alice"})

    assert "Secure" not in response.headers["set-cookie"]


async def test_session_cookie_can_be_marked_secure(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """https に移すときはこの設定だけを変える。"""
    monkeypatch.setattr(settings, "session_cookie_secure", True)

    response = await client.post("/api/auth/signup", json={"login_name": "alice"})

    assert "Secure" in response.headers["set-cookie"]


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


async def test_logout_leaves_other_devices_signed_in(
    client: AsyncClient, other_device: AsyncClient
) -> None:
    await signup(client)
    await other_device.post("/api/auth/login", json={"login_name": "alice"})

    await client.post("/api/auth/logout")

    assert (await other_device.get("/api/auth/me")).status_code == 200


@pytest.mark.parametrize("field", ["login_name", "display_name"])
async def test_name_of_32_characters_is_accepted(
    client: AsyncClient, field: str
) -> None:
    payload = {"login_name": "alice", field: "a" * 32}

    response = await client.post("/api/auth/signup", json=payload)

    assert response.status_code == 201


@pytest.mark.parametrize("field", ["login_name", "display_name"])
async def test_name_of_33_characters_is_rejected(
    client: AsyncClient, field: str
) -> None:
    """公開している上限そのものを固定する。

    実装の定数から期待値を作ると、上限を変えてもテストが緑のままになる。
    UI にも 32 と出すので、ここは実装と独立にリテラルで書く。
    """
    payload = {"login_name": "alice", field: "a" * 33}

    response = await client.post("/api/auth/signup", json=payload)

    assert response.status_code == 422


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
