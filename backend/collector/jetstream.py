from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone

import websockets

from backend.config import JETSTREAM_URL

logger = logging.getLogger(__name__)


class JetstreamCollector:
    def __init__(self, on_post: Callable[[dict], None]):
        self._on_post = on_post
        self._running = False
        self._ws = None
        self._reconnect_delay = 1

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self._connect()
            except Exception as e:
                logger.error(f"Jetstream connection error: {e}")
                if self._running:
                    logger.info(
                        f"Reconnecting in {self._reconnect_delay}s..."
                    )
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def _connect(self):
        # Subscribe to app.bsky.feed.post events
        url = f"{JETSTREAM_URL}?wantedCollections=app.bsky.feed.post"
        logger.info(f"Connecting to Jetstream: {url}")

        async with websockets.connect(url) as ws:
            self._ws = ws
            self._reconnect_delay = 1
            logger.info("Connected to Jetstream")

            async for message in ws:
                if not self._running:
                    break
                try:
                    event = json.loads(message)
                    post = self._extract_post(event)
                    if post:
                        self._on_post(post)
                except (json.JSONDecodeError, KeyError):
                    continue

    def _extract_post(self, event: dict) -> dict | None:
        if event.get("kind") != "commit":
            return None
        commit = event.get("commit", {})
        if commit.get("collection") != "app.bsky.feed.post":
            return None
        if commit.get("operation") != "create":
            return None

        record = commit.get("record", {})
        text = record.get("text", "")
        if not text:
            return None

        did = event.get("did", "")
        rkey = commit.get("rkey", "")
        created_at = record.get("createdAt", "")

        try:
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        # Extract reply parent external_id if this is a reply
        reply_to_id = None
        reply = record.get("reply")
        if reply:
            parent_uri = reply.get("parent", {}).get("uri", "")
            # URI format: at://did:plc:xxx/app.bsky.feed.post/rkey
            parts = parent_uri.split("/")
            if len(parts) >= 5 and parts[3] == "app.bsky.feed.post":
                parent_did = parts[2]  # did:plc:xxx
                parent_rkey = parts[4]
                reply_to_id = f"{parent_did}/{parent_rkey}"

        return {
            "external_id": f"{did}/{rkey}",
            "author_handle": did,
            "text": text,
            "created_at": ts,
            "source": "bluesky",
            "reply_to_id": reply_to_id,
        }

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()
