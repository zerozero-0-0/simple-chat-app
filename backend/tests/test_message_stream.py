"""WebSocket は同期の TestClient で叩く。

httpx は WebSocket を扱えず、TestClient は自前のイベントループでアプリを動かす。
非同期のフィクスチャとはループが違うので、このファイルだけファイルの DB を使い、
準備も TestClient 経由で行う。
"""

import itertools
import sqlite3
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect
from uvicorn.protocols.utils import ClientDisconnected

from app import main
from app.db import get_session
from app.deps import hash_token
from app.main import app
from app.models import User, utcnow
from app.routers import messages
from app.schemas import MessageResponse, MessageSender
from app.stream import MessageStream, stream


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override() -> object:
        async with factory() as session:
            yield session

    # lifespan がテーブルと共通の部屋を作る。本番と同じ経路を通す
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "session_factory", factory)
    app.dependency_overrides[get_session] = override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    # stream はプロセスで共有するので、次のテストに接続を持ち越さない
    wait_until(lambda: stream.count(SHARED_ROOM_ID) == 0)


# lifespan が作る部屋はこのファイルの使い捨て DB では必ず最初の 1 件
SHARED_ROOM_ID = 1


def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    """接続の登録と解除はサーバー側で非同期に起きるので、落ち着くまで待つ。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("状態が変わらないままタイムアウトしました")


def room_id(client: TestClient) -> str:
    return client.get("/api/rooms").json()[0]["public_id"]


def enter(client: TestClient, login_name: str) -> str:
    assert (
        client.post("/api/auth/signup", json={"login_name": login_name}).status_code
        == 201
    )
    public_id = room_id(client)
    assert client.post(f"/api/rooms/{public_id}/members").status_code == 200
    return public_id


def send(client: TestClient, public_id: str, body: str, client_message_id: str) -> None:
    response = client.post(
        f"/api/rooms/{public_id}/messages",
        json={"client_message_id": client_message_id, "body": body},
    )
    assert response.status_code == 201


def test_a_member_receives_a_message(client: TestClient) -> None:
    public_id = enter(client, "alice")

    with client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws:
        send(client, public_id, "やあ", "1")

        received = ws.receive_json()

    assert received["body"] == "やあ"
    assert received["sender"]["display_name"] == "alice"


def test_the_timestamp_carries_the_utc_offset(client: TestClient) -> None:
    public_id = enter(client, "alice")

    with client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws:
        send(client, public_id, "やあ", "1")

        assert ws.receive_json()["created_at"].endswith("+00:00")


def test_connecting_without_a_session_is_refused(client: TestClient) -> None:
    public_id = enter(client, "alice")
    client.post("/api/auth/logout")

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws,
    ):
        ws.receive_json()


def test_a_non_member_is_refused(client: TestClient) -> None:
    client.post("/api/auth/signup", json={"login_name": "alice"})
    public_id = room_id(client)

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws,
    ):
        ws.receive_json()


def test_an_unknown_room_is_refused(client: TestClient) -> None:
    client.post("/api/auth/signup", json={"login_name": "alice"})

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/rooms/deadbeef/messages/stream") as ws,
    ):
        ws.receive_json()


def test_a_resend_is_not_delivered_again(client: TestClient) -> None:
    """既に配ってあるので、再送では配り直さない。"""
    public_id = enter(client, "alice")

    with client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws:
        send(client, public_id, "やあ", "1")
        ws.receive_json()

        client.post(
            f"/api/rooms/{public_id}/messages",
            json={"client_message_id": "1", "body": "やあ"},
        )
        send(client, public_id, "つぎ", "2")

        assert ws.receive_json()["body"] == "つぎ"


def test_disconnecting_drops_the_connection(client: TestClient) -> None:
    public_id = enter(client, "alice")

    with client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws:
        send(client, public_id, "やあ", "1")
        ws.receive_json()  # 往復して、接続が登録されていることを確かめる

    wait_until(lambda: stream.count(SHARED_ROOM_ID) == 0)
    send(client, public_id, "つぎ", "2")  # 配る先が居なくても失敗しない


def test_logging_out_closes_the_stream(client: TestClient) -> None:
    """取り消したセッションにメッセージを流し続けないこと。"""
    public_id = enter(client, "alice")

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws,
    ):
        send(client, public_id, "やあ", "1")
        ws.receive_json()

        assert client.post("/api/auth/logout").status_code == 204
        ws.receive_json()

    wait_until(lambda: stream.count(SHARED_ROOM_ID) == 0)


def test_an_unexpected_frame_does_not_drop_the_connection(client: TestClient) -> None:
    """クライアントからは送らない前提だが、届いても切らないこと。"""
    public_id = enter(client, "alice")

    with client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws:
        ws.send_bytes(b"\x01\x02")

        send(client, public_id, "やあ", "1")

        assert ws.receive_json()["body"] == "やあ"


def test_logging_out_during_the_handshake_closes_the_stream(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """検証と登録の間にログアウトされても、接続を残さないこと。

    その順で起きると close_session が空振りするので、登録した後に
    セッションを確かめ直す必要がある。
    """
    public_id = enter(client, "alice")
    original = messages.find_session_user
    calls = itertools.count()

    async def revoked_after_the_first_look(db: AsyncSession, token: str) -> User | None:
        if next(calls):
            return None
        return await original(db, token)

    monkeypatch.setattr(messages, "find_session_user", revoked_after_the_first_look)

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws,
    ):
        ws.receive_json()

    wait_until(lambda: stream.count(SHARED_ROOM_ID) == 0)


def test_a_stream_already_closed_by_logout_ends_quietly(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """close_session が先に切っていても、確かめ直しが二重に閉じて落ちないこと。"""
    public_id = enter(client, "alice")
    original = messages.find_session_user
    calls = itertools.count()

    async def revoked_and_closed(db: AsyncSession, token: str) -> User | None:
        if next(calls):
            # ログアウトが先に接続を切った状況
            await stream.close_session(hash_token(token))
            return None
        return await original(db, token)

    monkeypatch.setattr(messages, "find_session_user", revoked_and_closed)

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/api/rooms/{public_id}/messages/stream") as ws,
    ):
        ws.receive_json()

    wait_until(lambda: stream.count(SHARED_ROOM_ID) == 0)


def add_room(db_path: Path, name: str) -> str:
    """部屋を作る API はまだ無いので、直接入れる。"""
    public_id = uuid4().hex
    created_at = datetime.now(UTC).replace(tzinfo=None).isoformat(" ")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO rooms (public_id, name, created_at) VALUES (?, ?, ?)",
            (public_id, name, created_at),
        )
    return public_id


def test_a_message_is_only_delivered_to_its_room(
    client: TestClient, db_path: Path
) -> None:
    """部屋で絞らないと、入っていない部屋の本文まで流れる。"""
    here = enter(client, "alice")
    there = add_room(db_path, "べつの部屋")
    assert client.post(f"/api/rooms/{there}/members").status_code == 200

    with (
        client.websocket_connect(f"/api/rooms/{here}/messages/stream") as ws_here,
        client.websocket_connect(f"/api/rooms/{there}/messages/stream") as ws_there,
    ):
        send(client, here, "こっちへ", "1")
        assert ws_here.receive_json()["body"] == "こっちへ"

        send(client, there, "あっちへ", "2")

        # 絞っていなければ、先に「こっちへ」が届く
        assert ws_there.receive_json()["body"] == "あっちへ"


def test_logging_out_leaves_other_sessions_connected(client: TestClient) -> None:
    """切るのはそのセッションの接続だけ。他の端末は残ること。"""
    public_id = enter(client, "alice")
    first = client.cookies["session_id"]
    client.post("/api/auth/login", json={"login_name": "alice"})
    second = client.cookies["session_id"]
    assert first != second

    client.cookies.set("session_id", first)
    with client.websocket_connect(f"/api/rooms/{public_id}/messages/stream"):
        client.cookies.set("session_id", second)
        with client.websocket_connect(
            f"/api/rooms/{public_id}/messages/stream"
        ) as kept:
            wait_until(lambda: stream.count(SHARED_ROOM_ID) == 2)

            client.cookies.set("session_id", first)
            assert client.post("/api/auth/logout").status_code == 204

            client.cookies.set("session_id", second)
            send(client, public_id, "やあ", "1")

            assert kept.receive_json()["body"] == "やあ"
            assert stream.count(SHARED_ROOM_ID) == 1


class FirstCallFails:
    """最初に触られた 1 本だけを失敗させる。

    接続は set で持つので走査順が決まらない。どれが先でも「先頭が失敗し、
    残りは処理される」を見られるようにする。
    """

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.used = False

    def check(self) -> None:
        if not self.used:
            self.used = True
            raise self.error


class FakeSocket:
    def __init__(self, gate: FirstCallFails) -> None:
        self.gate = gate
        self.closed = False
        self.received: list[dict[str, object]] = []

    async def close(self, code: int = 1000) -> None:
        self.gate.check()
        self.closed = True

    async def send_json(self, payload: dict[str, object]) -> None:
        self.gate.check()
        self.received.append(payload)


def three_sockets(connections: MessageStream) -> list[FakeSocket]:
    gate = FirstCallFails(ClientDisconnected())
    sockets = [FakeSocket(gate) for _ in range(3)]
    for socket in sockets:
        connections.add(1, "hash", cast(WebSocket, socket))
    return sockets


def a_message() -> MessageResponse:
    return MessageResponse(
        id=1,
        client_message_id="1",
        body="やあ",
        created_at=utcnow(),
        sender=MessageSender(public_id="x", display_name="alice"),
    )


async def test_closing_a_session_continues_past_a_dead_connection() -> None:
    """1 本切れなくても、残りを切り終えること。

    uvicorn は切断済みの接続への close を ClientDisconnected (OSError) にする。
    ここで抜けると、取り消したセッションの接続が残る。
    """
    connections = MessageStream()
    sockets = three_sockets(connections)

    await connections.close_session("hash")

    assert sum(socket.closed for socket in sockets) == 2
    assert connections.count(1) == 0


async def test_publishing_drops_a_dead_connection() -> None:
    """届かない接続は捨てて、他の宛先への配信を止めないこと。"""
    connections = MessageStream()
    sockets = three_sockets(connections)

    await connections.publish(1, a_message())

    delivered = [payload["body"] for socket in sockets for payload in socket.received]
    assert delivered == ["やあ", "やあ"]
    assert connections.count(1) == 2
