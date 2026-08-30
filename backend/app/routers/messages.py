from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession, MemberRoom
from app.models import Message
from app.schemas import MessageCreateRequest, MessageResponse

router = APIRouter(prefix="/rooms/{public_id}/messages", tags=["messages"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: MessageCreateRequest,
    room: MemberRoom,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> MessageResponse:
    """メッセージを送る。同じ `client_message_id` の再送では 2 通にならない。"""
    # rollback すると room と user の属性が失効し、非同期では読み直せない
    room_id = room.id
    sender_id = user.id

    message = Message(
        room=room,
        sender=user,
        client_message_id=payload.client_message_id,
        body=payload.body,
    )
    db.add(message)
    try:
        # 再送は (room_id, sender_id, client_message_id) の一意制約で弾く
        await db.commit()
    except IntegrityError:
        await db.rollback()
        response.status_code = status.HTTP_200_OK
        return await _find_resent(db, room_id, sender_id, payload.client_message_id)

    return MessageResponse.model_validate(message)


@router.get("")
async def list_messages(
    room: MemberRoom,
    db: DbSession,
    after: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    """`after` より後のメッセージを古い順に返す。"""
    query = (
        select(Message)
        .where(Message.room_id == room.id)
        .options(selectinload(Message.sender))
        .order_by(Message.id)
        .limit(limit)
    )
    if after is not None:
        query = query.where(Message.id > after)

    messages = (await db.scalars(query)).all()
    return [MessageResponse.model_validate(message) for message in messages]


async def _find_resent(
    db: DbSession, room_id: int, sender_id: int, client_message_id: str
) -> MessageResponse:
    message = await db.scalar(
        select(Message)
        .where(
            Message.room_id == room_id,
            Message.sender_id == sender_id,
            Message.client_message_id == client_message_id,
        )
        .options(selectinload(Message.sender))
    )
    if message is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "メッセージを取得できませんでした"
        )

    return MessageResponse.model_validate(message)
