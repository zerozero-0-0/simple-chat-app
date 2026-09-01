from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, WebSocket, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.websockets import WebSocketDisconnect

from app.deps import (
    SESSION_COOKIE_NAME,
    CurrentUser,
    DbSession,
    MemberRoom,
    find_session_user,
    get_member_room,
    hash_token,
)
from app.models import Message, Room
from app.schemas import MessageCreateRequest, MessageResponse
from app.stream import close_quietly, stream

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
        resent = await _find_resent(db, room_id, sender_id, payload.client_message_id)
        if resent is None:
            # 再送ではない衝突。原因を握りつぶさない
            raise

        # 既に配ってあるので、配り直さない
        response.status_code = status.HTTP_200_OK
        return resent

    sent = MessageResponse.model_validate(message)
    await stream.publish(room_id, sent)
    return sent


@router.get("")
async def list_messages(
    room: MemberRoom,
    db: DbSession,
    after: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    """メッセージを古い順に返す。

    `after` を渡すとその ID より後を古い方から、渡さなければ最後の `limit` 件。
    画面を開いたときに見たいのは直近のやりとりで、`after` は切断していた間に
    取りこぼした分を追いかけるのに使う。
    """
    query = (
        select(Message)
        .where(Message.room_id == room.id)
        .options(selectinload(Message.sender))
        .limit(limit)
    )

    if after is not None:
        query = query.where(Message.id > after).order_by(Message.id)
        messages = list((await db.scalars(query)).all())
    else:
        # 新しい方から limit 件を取り、返すときに古い順へ戻す
        query = query.order_by(Message.id.desc())
        messages = list(reversed((await db.scalars(query)).all()))

    return [MessageResponse.model_validate(message) for message in messages]


async def _find_resent(
    db: DbSession, room_id: int, sender_id: int, client_message_id: str
) -> MessageResponse | None:
    """同じ送信者が同じ `client_message_id` で送った既存のメッセージ。"""
    message = await db.scalar(
        select(Message)
        .where(
            Message.room_id == room_id,
            Message.sender_id == sender_id,
            Message.client_message_id == client_message_id,
        )
        .options(selectinload(Message.sender))
    )
    return MessageResponse.model_validate(message) if message is not None else None


@router.websocket("/stream")
async def stream_messages(websocket: WebSocket, public_id: str, db: DbSession) -> None:
    """つないでいる間、新しいメッセージを受け取る。

    切断中に届いたものは `GET ?after=<id>` で取り直す。
    """
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    room = await _accept(websocket, public_id, db)
    if room is None or token is None:
        return

    room_id = room.id
    stream.add(room_id, hash_token(token), websocket)

    # 登録するまでの間にログアウトされると、close_session が空振りしたまま
    # 取り消し済みのセッションで登録が残る。登録してから確かめ直す
    if await find_session_user(db, token) is None:
        stream.remove(websocket)
        # close_session が先に切っている場合がある
        await close_quietly(websocket)
        return

    # 接続が続く間セッションを握らないよう、認証が済んだら閉じる
    await db.close()
    try:
        while True:
            # クライアントからは送らない。切断を知るために読む。フレームの
            # 種別に依らないよう receive_text ではなく receive を使う
            if (await websocket.receive())["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        stream.remove(websocket)


async def _accept(websocket: WebSocket, public_id: str, db: DbSession) -> Room | None:
    """認証と入室を確かめて接続を受ける。断るときは None を返す。"""
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    user = await find_session_user(db, token) if token is not None else None
    if user is None:
        await close_quietly(websocket)
        return None

    try:
        room = await get_member_room(public_id, user, db)
    except HTTPException:
        await close_quietly(websocket)
        return None

    await websocket.accept()
    return room
