import unicodedata
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


async def test_using_a_session_extends_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    """使っている限りログアウトされないこと。"""
    await signup(client)
    ttl = timedelta(hours=settings.session_ttl_hours)
    stored = await session.scalar(select(Session))
    assert stored is not None
    stored.expires_at = utcnow() + ttl / 4
    await session.commit()

    await client.get("/api/auth/me")

    await session.refresh(stored)
    assert stored.expires_at > utcnow() + ttl * 0.9


async def test_every_authenticated_request_refreshes_the_cookie(
    client: AsyncClient,
) -> None:
    """DB を書かないときも Cookie は貼り直すこと。

    エラー応答では依存関係が載せた Set-Cookie が捨てられる。延長したときだけ
    貼り直すと、一度ずれた期限が戻らないまま Cookie が先に切れる。
    """
    await signup(client)

    response = await client.get("/api/auth/me")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert f"Max-Age={settings.session_ttl_hours * 3600}" in cookie


async def test_a_session_with_time_left_is_not_written_again(
    client: AsyncClient, session: AsyncSession
) -> None:
    """読むだけのリクエストで毎回 DB に書かないこと。"""
    await signup(client)
    stored = await session.scalar(select(Session))
    assert stored is not None
    before = stored.expires_at

    await client.get("/api/auth/me")

    await session.refresh(stored)
    assert stored.expires_at == before


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


async def test_a_login_name_may_be_japanese(client: AsyncClient) -> None:
    """`login_name` は URL に出ないので、文字種を絞る理由がない。"""
    response = await client.post("/api/auth/signup", json={"login_name": "アリス"})

    assert response.status_code == 201
    assert response.json()["login_name"] == "アリス"


async def test_a_name_may_contain_a_space(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "山田 太郎"})

    assert response.status_code == 201
    assert response.json()["login_name"] == "山田 太郎"


async def test_a_name_is_trimmed(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": "  alice  "})

    assert response.status_code == 201
    assert response.json()["login_name"] == "alice"


@pytest.mark.parametrize("name", ["   ", "\n"])
async def test_a_blank_name_is_rejected(client: AsyncClient, name: str) -> None:
    """空白だけの名前は、一覧で送信者が空欄に見える。"""
    response = await client.post("/api/auth/signup", json={"login_name": name})

    assert response.status_code == 422


async def test_the_same_name_in_another_unicode_form_is_the_same_user(
    client: AsyncClient,
) -> None:
    """見た目が同じ名前が別のユーザーにならないこと。

    macOS の入力やペーストでは「が」が「か + 濁点」の分解形で届くことがある。
    """
    decomposed = unicodedata.normalize("NFD", "がっこう")
    assert decomposed != "がっこう"
    await client.post("/api/auth/signup", json={"login_name": decomposed})
    await client.post("/api/auth/logout")

    response = await client.post("/api/auth/login", json={"login_name": "がっこう"})

    assert response.status_code == 200


async def test_an_empty_login_name_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"login_name": ""})

    assert response.status_code == 422


async def test_public_id_differs_from_internal_id(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signup(client)

    user = await session.scalar(select(User))

    assert user is not None
    assert user.public_id != str(user.id)
