from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, conv_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[conv_id].add(ws)

    def disconnect(self, conv_id: int, ws: WebSocket) -> None:
        self._connections[conv_id].discard(ws)
        if not self._connections[conv_id]:
            self._connections.pop(conv_id, None)

    async def broadcast(self, conv_id: int, payload: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(conv_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(conv_id, ws)


manager = ConnectionManager()
