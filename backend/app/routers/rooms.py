from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbSession
from app.models import Room, RoomMember
from app.schemas import RoomResponse

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("")
async def list_rooms(user: CurrentUser, db: DbSession) -> list[RoomResponse]:
    rooms = (await db.scalars(select(Room).order_by(Room.id))).all()
    return [RoomResponse.model_validate(room) for room in rooms]


@router.post("/{public_id}/members")
async def join_room(public_id: str, user: CurrentUser, db: DbSession) -> RoomResponse:
    """部屋に入る。何度呼んでも同じ結果になる。"""
    room = await db.scalar(select(Room).where(Room.public_id == public_id))
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "その部屋はありません")

    # rollback すると room の属性が失効し、非同期では読み直せない
    joined = RoomResponse.model_validate(room)

    db.add(RoomMember(room_id=room.id, user_id=user.id))
    try:
        # 二重の参加は (room_id, user_id) の一意制約で弾く
        await db.commit()
    except IntegrityError:
        await db.rollback()

    return joined
