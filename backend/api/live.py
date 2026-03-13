import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.config import SSE_BUFFER_SIZE

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared state for SSE broadcasting
_post_buffer: deque[dict] = deque(maxlen=SSE_BUFFER_SIZE)
_subscribers: list[asyncio.Queue] = []
_stats = {"connected": False, "post_count": 0, "last_minute_count": 0}


def broadcast_post(post_data: dict):
    """Called by the pipeline when a new post is analyzed."""
    _post_buffer.append(post_data)
    _stats["post_count"] += 1
    event = {"type": "new_post", "data": post_data}
    for queue in _subscribers:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def broadcast_ranking_update(ranking_data: list[dict]):
    """Called by the snapshot task when rankings are recalculated."""
    event = {"type": "ranking_update", "data": ranking_data}
    for queue in _subscribers:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def broadcast_match_event(match_event: dict):
    """Called when a match event (goal, card) is added."""
    event = {"type": "match_event", "data": match_event}
    for queue in _subscribers:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def set_connected(connected: bool):
    _stats["connected"] = connected


@router.get("/live/feed")
async def live_feed():
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)

    async def event_generator():
        try:
            # Send recent posts as initial batch
            for post in _post_buffer:
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "new_post", "data": post}),
                }

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {
                        "event": "message",
                        "data": json.dumps(event),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        finally:
            _subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@router.get("/live/status")
def live_status():
    from backend.models.database import SessionLocal
    from backend.models.match import Match

    db = SessionLocal()
    try:
        active = db.query(Match).filter(Match.status == "live").count()
    finally:
        db.close()

    return {
        "connected": _stats["connected"],
        "posts_per_minute": _stats.get("last_minute_count", 0),
        "active_matches": active,
        "total_posts_collected": _stats["post_count"],
    }
