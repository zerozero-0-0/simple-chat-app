from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Room
from app.routers import messages


async def enter(client: AsyncClient, room: Room, login_name: str = "alice") -> None:
    signup = await client.post("/api/auth/signup", json={"login_name": login_name})
    assert signup.status_code == 201
    joined = await client.post(f"/api/rooms/{room.public_id}/members")
    assert joined.status_code == 200


def payload(body: str = "こんにちは", client_message_id: str = "c1") -> dict[str, str]:
    return {"client_message_id": client_message_id, "body": body}


async def test_sending_a_message_returns_it(client: AsyncClient, room: Room) -> None:
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload()
    )

    assert response.status_code == 201
    body = response.json()
    assert body["body"] == "こんにちは"
    assert body["client_message_id"] == "c1"
    assert body["sender"]["display_name"] == "alice"


async def test_the_timestamp_carries_the_utc_offset(
    client: AsyncClient, room: Room
) -> None:
    """オフセットが無いと、ブラウザがローカル時刻として読んでずれる。"""
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload()
    )

    created_at = datetime.fromisoformat(response.json()["created_at"])
    assert created_at.utcoffset() == timedelta(0)


async def test_the_sender_is_shown_without_the_login_name(
    client: AsyncClient, room: Room
) -> None:
    """他のユーザーにも見える表現には `login_name` を出さない。"""
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload()
    )

    assert "login_name" not in response.json()["sender"]


async def test_resending_does_not_create_a_second_message(
    client: AsyncClient, session: AsyncSession, room: Room
) -> None:
    await enter(client, room)

    first = await client.post(f"/api/rooms/{room.public_id}/messages", json=payload())
    again = await client.post(f"/api/rooms/{room.public_id}/messages", json=payload())

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json() == first.json()
    assert await session.scalar(select(func.count()).select_from(Message)) == 1


async def test_two_users_may_pick_the_same_client_id(
    client: AsyncClient,
    other_device: AsyncClient,
    session: AsyncSession,
    room: Room,
) -> None:
    """採番が衝突しても、後から送った人のメッセージが消えないこと。"""
    await enter(client, room, "alice")
    await enter(other_device, room, "bob")

    first = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload("alice から", "1")
    )
    second = await other_device.post(
        f"/api/rooms/{room.public_id}/messages", json=payload("bob から", "1")
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["body"] == "bob から"
    assert second.json()["sender"]["display_name"] == "bob"
    assert await session.scalar(select(func.count()).select_from(Message)) == 2


async def test_resending_is_matched_per_sender(
    client: AsyncClient, other_device: AsyncClient, session: AsyncSession, room: Room
) -> None:
    """他人が同じ id を使っていても、自分の再送は自分のメッセージを返すこと。"""
    await enter(client, room, "alice")
    await enter(other_device, room, "bob")
    await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload("alice から", "1")
    )
    await other_device.post(
        f"/api/rooms/{room.public_id}/messages", json=payload("bob から", "1")
    )

    again = await other_device.post(
        f"/api/rooms/{room.public_id}/messages", json=payload("bob から", "1")
    )

    assert again.status_code == 200
    assert again.json()["body"] == "bob から"
    assert await session.scalar(select(func.count()).select_from(Message)) == 2


async def test_the_same_client_id_in_another_room_is_a_new_message(
    client: AsyncClient, session: AsyncSession, room: Room, other_room: Room
) -> None:
    """一意制約は部屋ごと。別の部屋なら同じ id でも別のメッセージになる。"""
    await enter(client, room)
    await client.post(f"/api/rooms/{other_room.public_id}/members")

    await client.post(f"/api/rooms/{room.public_id}/messages", json=payload())
    await client.post(f"/api/rooms/{other_room.public_id}/messages", json=payload())

    assert await session.scalar(select(func.count()).select_from(Message)) == 2


async def test_listing_returns_messages_oldest_first(
    client: AsyncClient, room: Room
) -> None:
    await enter(client, room)
    for index in range(3):
        await client.post(
            f"/api/rooms/{room.public_id}/messages",
            json=payload(f"body{index}", f"c{index}"),
        )

    response = await client.get(f"/api/rooms/{room.public_id}/messages")

    assert [message["body"] for message in response.json()] == [
        "body0",
        "body1",
        "body2",
    ]


async def test_after_returns_only_newer_messages(
    client: AsyncClient, room: Room
) -> None:
    await enter(client, room)
    sent = [
        (
            await client.post(
                f"/api/rooms/{room.public_id}/messages",
                json=payload(f"body{index}", f"c{index}"),
            )
        ).json()
        for index in range(3)
    ]

    response = await client.get(
        f"/api/rooms/{room.public_id}/messages", params={"after": sent[0]["id"]}
    )

    assert [message["id"] for message in response.json()] == [
        sent[1]["id"],
        sent[2]["id"],
    ]


async def test_limit_caps_the_number_of_messages(
    client: AsyncClient, room: Room
) -> None:
    await enter(client, room)
    for index in range(3):
        await client.post(
            f"/api/rooms/{room.public_id}/messages",
            json=payload(f"body{index}", f"c{index}"),
        )

    response = await client.get(
        f"/api/rooms/{room.public_id}/messages", params={"limit": 2}
    )

    assert len(response.json()) == 2


async def test_listing_returns_the_latest_messages(
    client: AsyncClient, room: Room
) -> None:
    """画面を開いたときに出るのが直近のやりとりであること。

    古い方から返すと、発言が溜まった部屋では最初の 50 件で止まったまま
    今のやりとりが見えない。
    """
    await enter(client, room)
    for index in range(5):
        await client.post(
            f"/api/rooms/{room.public_id}/messages",
            json=payload(f"body{index}", f"c{index}"),
        )

    response = await client.get(
        f"/api/rooms/{room.public_id}/messages", params={"limit": 3}
    )

    assert [message["body"] for message in response.json()] == [
        "body2",
        "body3",
        "body4",
    ]


async def test_after_walks_forward_from_the_cursor(
    client: AsyncClient, room: Room
) -> None:
    """取りこぼしは古い方から順に追いつけること。"""
    await enter(client, room)
    sent = [
        (
            await client.post(
                f"/api/rooms/{room.public_id}/messages",
                json=payload(f"body{index}", f"c{index}"),
            )
        ).json()
        for index in range(5)
    ]

    response = await client.get(
        f"/api/rooms/{room.public_id}/messages",
        params={"after": sent[0]["id"], "limit": 2},
    )

    assert [message["body"] for message in response.json()] == ["body1", "body2"]


async def test_messages_from_another_room_are_not_listed(
    client: AsyncClient, room: Room, other_room: Room
) -> None:
    await enter(client, room)
    await client.post(f"/api/rooms/{other_room.public_id}/members")
    await client.post(f"/api/rooms/{other_room.public_id}/messages", json=payload())

    response = await client.get(f"/api/rooms/{room.public_id}/messages")

    assert response.json() == []


async def test_a_non_member_cannot_send(client: AsyncClient, room: Room) -> None:
    await client.post("/api/auth/signup", json={"login_name": "alice"})

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload()
    )

    assert response.status_code == 403


async def test_a_non_member_cannot_list(client: AsyncClient, room: Room) -> None:
    await client.post("/api/auth/signup", json={"login_name": "alice"})

    response = await client.get(f"/api/rooms/{room.public_id}/messages")

    assert response.status_code == 403


async def test_sending_requires_a_session(client: AsyncClient, room: Room) -> None:
    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload()
    )

    assert response.status_code == 401


async def test_listing_requires_a_session(client: AsyncClient, room: Room) -> None:
    response = await client.get(f"/api/rooms/{room.public_id}/messages")

    assert response.status_code == 401


async def test_an_unknown_room_looks_the_same_before_login(
    client: AsyncClient, room: Room
) -> None:
    """ログイン前は、部屋の有無も入室状態も返さないこと。"""
    known = await client.get(f"/api/rooms/{room.public_id}/messages")
    unknown = await client.get("/api/rooms/deadbeef/messages")

    assert known.status_code == 401
    assert unknown.status_code == 401


async def test_a_conflict_that_is_not_a_resend_is_not_reported_as_success(
    client: AsyncClient, room: Room, monkeypatch: pytest.MonkeyPatch
) -> None:
    """再送として取り出せない衝突を 200 にしないこと。"""
    await enter(client, room)
    await client.post(f"/api/rooms/{room.public_id}/messages", json=payload())

    async def not_found(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(messages, "_find_resent", not_found)

    with pytest.raises(IntegrityError):
        await client.post(f"/api/rooms/{room.public_id}/messages", json=payload())


async def test_sending_to_an_unknown_room_is_rejected(client: AsyncClient) -> None:
    await client.post("/api/auth/signup", json={"login_name": "alice"})

    response = await client.post("/api/rooms/deadbeef/messages", json=payload())

    assert response.status_code == 404


async def test_a_message_may_contain_an_emoji(client: AsyncClient, room: Room) -> None:
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload("やあ🌸")
    )

    assert response.status_code == 201
    assert response.json()["body"] == "やあ🌸"


async def test_an_empty_body_is_rejected(client: AsyncClient, room: Room) -> None:
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload(body="")
    )

    assert response.status_code == 422


async def test_a_body_over_the_limit_is_rejected(
    client: AsyncClient, room: Room
) -> None:
    """UI に出す上限と実際に弾く長さがずれないこと。"""
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload(body="あ" * 1001)
    )

    assert response.status_code == 422


async def test_a_body_at_the_limit_is_accepted(client: AsyncClient, room: Room) -> None:
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload(body="あ" * 1000)
    )

    assert response.status_code == 201


@pytest.mark.parametrize("body", ["   ", "\n", "\t "])
async def test_a_blank_body_is_rejected(
    client: AsyncClient, room: Room, body: str
) -> None:
    """空白だけの発言は一覧で空の吹き出しになる。"""
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload(body=body)
    )

    assert response.status_code == 422


async def test_a_body_is_trimmed(client: AsyncClient, room: Room) -> None:
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload(body="  やあ  ")
    )

    assert response.json()["body"] == "やあ"


async def test_a_body_is_measured_after_trimming(
    client: AsyncClient, room: Room
) -> None:
    """前後の空白で上限を超えたことにされないこと。"""
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages",
        json=payload(body="  " + "あ" * 1000 + "  "),
    )

    assert response.status_code == 201


async def test_a_body_keeps_its_inner_line_breaks(
    client: AsyncClient, room: Room
) -> None:
    await enter(client, room)

    response = await client.post(
        f"/api/rooms/{room.public_id}/messages", json=payload(body="いち\nに")
    )

    assert response.json()["body"] == "いち\nに"
