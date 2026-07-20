"""WebSocket 连接管理：按 job_id 推送进度。

设计：
- 每个 job_id 维护一组 WebSocket 连接（同一作业可被多个前端页面订阅）
- publish(job_id, event) 将事件异步发送给所有订阅者
- 事件结构: {"type": "stage_update"|"item_update"|"job_update", "payload": {...}}
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, Dict, Set

from fastapi import WebSocket

# job_id -> set[WebSocket]
_connections: Dict[int, Set[WebSocket]] = defaultdict(set)
_lock = asyncio.Lock()


class WebSocketManager:
    """管理 WebSocket 连接并按 job_id 推送进度。"""

    async def connect(self, job_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with _lock:
            _connections[job_id].add(ws)

    async def disconnect(self, job_id: int, ws: WebSocket) -> None:
        async with _lock:
            if ws in _connections.get(job_id, set()):
                _connections[job_id].discard(ws)
            if not _connections.get(job_id):
                _connections.pop(job_id, None)

    async def publish(self, job_id: int, event_type: str, payload: Any) -> None:
        """向某 job 的所有订阅者推送事件。"""
        async with _lock:
            sockets = list(_connections.get(job_id, set()))
        message = json.dumps(
            {"type": event_type, "job_id": job_id, "payload": payload},
            ensure_ascii=False,
            default=str,
        )
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with _lock:
                for ws in dead:
                    _connections.get(job_id, set()).discard(ws)

    async def broadcast(self, event_type: str, payload: Any) -> None:
        """广播给所有连接。"""
        async with _lock:
            all_job_ids = list(_connections.keys())
        for jid in all_job_ids:
            await self.publish(jid, event_type, payload)


ws_manager = WebSocketManager()
