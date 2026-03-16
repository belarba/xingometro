"""Collector that polls Brazilian football subreddits via Reddit API."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE = "https://oauth.reddit.com"
_USER_AGENT = "xingometro/1.0"
_MAX_SEEN = 10_000


class RedditCollector:
    def __init__(
        self,
        on_post: Callable[[dict], None],
        client_id: str,
        client_secret: str,
        subreddits: list[str],
        poll_interval: int = 30,
    ):
        self._on_post = on_post
        self._client_id = client_id
        self._client_secret = client_secret
        self._subreddits = subreddits
        self._poll_interval = poll_interval
        self._running = False
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._seen_ids: set[str] = set()
        self._backoff = 1

    async def start(self):
        """Main polling loop."""
        self._running = True
        logger.info(
            "RedditCollector started (%d subreddits)", len(self._subreddits)
        )

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            while self._running:
                try:
                    await self._poll_cycle(client)
                    self._backoff = 1
                except Exception as e:
                    logger.error("Reddit poll error: %s", e)
                    self._backoff = min(self._backoff * 2, 300)

                await asyncio.sleep(
                    self._poll_interval if self._backoff == 1 else self._backoff
                )

    async def stop(self):
        """Stop the polling loop."""
        self._running = False
        logger.info("RedditCollector stopped")

    async def _ensure_token(self, client: httpx.AsyncClient):
        """Fetch or refresh OAuth2 token using client credentials."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return

        resp = await client.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        logger.info("Reddit OAuth token refreshed")

    async def _poll_cycle(self, client: httpx.AsyncClient):
        """One poll cycle: fetch new posts and comments from all subreddits."""
        await self._ensure_token(client)

        for sub in self._subreddits:
            if not self._running:
                break

            # Fetch new posts
            items = await self._fetch_listing(
                client, f"{_API_BASE}/r/{sub}/new.json", {"limit": 25, "raw_json": 1}
            )
            for item in items:
                post = self._extract_item(item, "post")
                if post and post["external_id"] not in self._seen_ids:
                    self._seen_ids.add(post["external_id"])
                    self._on_post(post)

            # Fetch new comments
            items = await self._fetch_listing(
                client, f"{_API_BASE}/r/{sub}/comments.json", {"limit": 50, "raw_json": 1}
            )
            for item in items:
                post = self._extract_item(item, "comment")
                if post and post["external_id"] not in self._seen_ids:
                    self._seen_ids.add(post["external_id"])
                    self._on_post(post)

        # Prevent unbounded memory growth
        if len(self._seen_ids) > _MAX_SEEN:
            self._seen_ids.clear()

    async def _fetch_listing(
        self, client: httpx.AsyncClient, url: str, params: dict
    ) -> list:
        """Fetch a Reddit listing endpoint, handle rate limits."""
        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            resp = await client.get(url, headers=headers, params=params)

            # Rate limit check
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining is not None and float(remaining) < 10:
                reset = float(resp.headers.get("x-ratelimit-reset", "60"))
                logger.warning(
                    "Reddit rate limit low (%.0f remaining), sleeping %.0fs",
                    float(remaining),
                    reset,
                )
                await asyncio.sleep(min(reset, 120))

            if resp.status_code == 429:
                reset = float(resp.headers.get("x-ratelimit-reset", "60"))
                logger.warning("Reddit 429, sleeping %.0fs", reset)
                await asyncio.sleep(min(reset, 120))
                return []

            if resp.status_code == 401:
                # Token expired, force refresh on next call
                self._access_token = None
                return []

            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("children", [])

        except httpx.TimeoutException:
            logger.warning("Reddit timeout for %s", url)
            return []
        except httpx.HTTPError as e:
            logger.warning("Reddit HTTP error: %s", e)
            return []

    @staticmethod
    def _extract_item(thing: dict, item_type: str) -> Optional[dict]:
        """Extract a normalized post dict from a Reddit 'thing'."""
        data = thing.get("data", {})

        author = data.get("author", "")
        if not author or author in ("[deleted]", "[removed]", "AutoModerator"):
            return None

        if item_type == "comment":
            text = data.get("body", "")
        else:
            text = data.get("selftext") or data.get("title", "")

        if not text or len(text) < 5:
            return None

        name = data.get("name", "")
        if not name:
            return None

        created_utc = data.get("created_utc", 0)
        try:
            ts = datetime.fromtimestamp(created_utc, tz=timezone.utc)
        except (ValueError, OSError):
            ts = datetime.now(timezone.utc)

        return {
            "external_id": f"reddit_{name}",
            "author_handle": f"u/{author}",
            "text": text,
            "created_at": ts,
            "source": "reddit",
        }
