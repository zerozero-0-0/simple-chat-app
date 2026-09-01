import pytest
from httpx import AsyncClient


async def allowed_origin(client: AsyncClient, origin: str) -> str | None:
    """プリフライトが返す許可オリジン。許されなければ None。"""
    response = await client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return response.headers.get("access-control-allow-origin")


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3100",
        "http://[::1]:3100",
    ],
)
async def test_any_local_port_is_allowed(client: AsyncClient, origin: str) -> None:
    """手元で上げたフロントは、ポートが変わっても通ること。

    `next dev` は 3000 が埋まっていれば 3001 で上がる。ポートを 1 つに
    決め打つと、2 つ目を上げた瞬間にすべての API が CORS で弾かれる。
    """
    assert await allowed_origin(client, origin) == origin


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example",
        "http://localhost.evil.example:3000",
        "https://localhost:3000",
        "http://localhost",
    ],
)
async def test_an_origin_outside_the_machine_is_refused(
    client: AsyncClient, origin: str
) -> None:
    """Cookie の付く要求を、手元以外のページから出させないこと。

    許すのは `http://<ループバック>:<ポート>` の形だけ。名前の一部に
    localhost を含むホストや、ポートの無いオリジンは通さない。
    """
    assert await allowed_origin(client, origin) is None
