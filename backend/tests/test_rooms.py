from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Room, RoomMember


async def signup(client: AsyncClient, login_name: str = "alice") -> None:
    response = await client.post("/api/auth/signup", json={"login_name": login_name})
    assert response.status_code == 201


async def test_listing_rooms_requires_a_session(
    client: AsyncClient, room: Room
) -> None:
    response = await client.get("/api/rooms")

    assert response.status_code == 401


async def test_listing_rooms_returns_the_shared_room(
    client: AsyncClient, room: Room
) -> None:
    await signup(client)

    response = await client.get("/api/rooms")

    assert response.status_code == 200
    assert response.json() == [{"public_id": room.public_id, "name": room.name}]


async def test_joining_makes_the_user_a_member(
    client: AsyncClient, session: AsyncSession, room: Room
) -> None:
    await signup(client)

    response = await client.post(f"/api/rooms/{room.public_id}/members")

    assert response.status_code == 200
    assert response.json()["public_id"] == room.public_id
    assert await session.scalar(select(func.count()).select_from(RoomMember)) == 1


async def test_joining_twice_leaves_one_membership(
    client: AsyncClient, session: AsyncSession, room: Room
) -> None:
    """入室は何度呼んでも同じ結果になること。"""
    await signup(client)

    await client.post(f"/api/rooms/{room.public_id}/members")
    response = await client.post(f"/api/rooms/{room.public_id}/members")

    assert response.status_code == 200
    assert await session.scalar(select(func.count()).select_from(RoomMember)) == 1


async def test_joining_an_unknown_room_is_rejected(client: AsyncClient) -> None:
    await signup(client)

    response = await client.post("/api/rooms/deadbeef/members")

    assert response.status_code == 404


async def test_joining_requires_a_session(client: AsyncClient, room: Room) -> None:
    response = await client.post(f"/api/rooms/{room.public_id}/members")

    assert response.status_code == 401


async def test_each_user_gets_their_own_membership(
    client: AsyncClient, other_device: AsyncClient, session: AsyncSession, room: Room
) -> None:
    await signup(client, "alice")
    await signup(other_device, "bob")

    await client.post(f"/api/rooms/{room.public_id}/members")
    await other_device.post(f"/api/rooms/{room.public_id}/members")

    assert await session.scalar(select(func.count()).select_from(RoomMember)) == 2


async def test_a_new_member_has_read_nothing(
    client: AsyncClient, session: AsyncSession, room: Room
) -> None:
    await signup(client)

    await client.post(f"/api/rooms/{room.public_id}/members")

    member = await session.scalar(select(RoomMember))
    assert member is not None
    assert member.last_read_message_id is None


async def test_public_id_differs_from_internal_id(
    session: AsyncSession, room: Room
) -> None:
    assert room.public_id != str(room.id)
