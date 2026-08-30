"""部屋ごとの WebSocket 接続をまとめ、新しいメッセージを配る。

配るのはつながっている間だけ。切断中に届いたものは、クライアントが
`GET /api/rooms/{public_id}/messages?after=<id>` で取り直す。

接続はセッションごとにも引けるようにしてある。ログアウトしたセッションの
接続をその場で切るため。
"""

from collections import defaultdict
from contextlib import suppress

from fastapi import WebSocket, status
from starlette.websockets import WebSocketDisconnect

from app.schemas import MessageResponse

# 切断済みの接続を操作したときに上がるもの。uvicorn は送信も close も
# ClientDisconnected (OSError) にして投げる
DISCONNECTED = (OSError, RuntimeError, WebSocketDisconnect)


async def close_quietly(websocket: WebSocket) -> None:
    """接続を切る。既に切れていれば何もしない。"""
    with suppress(*DISCONNECTED):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


class MessageStream:
    def __init__(self) -> None:
        self._by_room: dict[int, set[WebSocket]] = defaultdict(set)
        self._by_session: dict[str, set[WebSocket]] = defaultdict(set)
        self._keys: dict[WebSocket, tuple[int, str]] = {}

    def add(self, room_id: int, token_hash: str, websocket: WebSocket) -> None:
        self._by_room[room_id].add(websocket)
        self._by_session[token_hash].add(websocket)
        self._keys[websocket] = (room_id, token_hash)

    def remove(self, websocket: WebSocket) -> None:
        """何度呼んでも同じ結果になる。"""
        key = self._keys.pop(websocket, None)
        if key is None:
            return

        room_id, token_hash = key
        _discard(self._by_room, room_id, websocket)
        _discard(self._by_session, token_hash, websocket)

    def count(self, room_id: int) -> int:
        return len(self._by_room.get(room_id, ()))

    async def publish(self, room_id: int, message: MessageResponse) -> None:
        """部屋の全員に配る。届かない接続は捨てて、送信側は止めない。"""
        payload = message.model_dump(mode="json")
        for websocket in tuple(self._by_room.get(room_id, ())):
            try:
                await websocket.send_json(payload)
            except DISCONNECTED:
                self.remove(websocket)

    async def close_session(self, token_hash: str) -> None:
        """そのセッションで張られた接続を切る。

        セッションを見るのは接続時の 1 回だけなので、ログアウトを伝えないと
        取り消したはずのセッションにメッセージが流れ続ける。
        """
        for websocket in tuple(self._by_session.get(token_hash, ())):
            self.remove(websocket)
            await close_quietly(websocket)


def _discard[K](index: dict[K, set[WebSocket]], key: K, websocket: WebSocket) -> None:
    group = index.get(key)
    if group is None:
        return

    group.discard(websocket)
    if not group:
        del index[key]


stream = MessageStream()
