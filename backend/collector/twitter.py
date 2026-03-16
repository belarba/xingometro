"""Twitter/X collector with 3-layer fallback: twscrape → ntscraper → xcancel scraping."""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx

from backend.models.database import SessionLocal
from backend.models.match import Match
from backend.models.team import Team

logger = logging.getLogger(__name__)

_MAX_SEEN = 50_000
_USER_AGENT = "xingometro/1.0"


# ---------------------------------------------------------------------------
# Raw tweet dataclass-like dict
# ---------------------------------------------------------------------------
# {
#   "external_id": "tw_1234567890",
#   "author_handle": "@usuario",
#   "text": "...",
#   "created_at": datetime,
#   "source": "twitter",
# }


# ---------------------------------------------------------------------------
# Adaptive polling state machine (reuses football_api pattern)
# ---------------------------------------------------------------------------
class _State(Enum):
    IDLE = "idle"
    WARMUP = "warmup"
    LIVE = "live"
    COOLDOWN = "cooldown"


_INTERVALS = {
    _State.IDLE: 30 * 60,     # 30 min
    _State.WARMUP: 5 * 60,    # 5 min
    _State.LIVE: 2 * 60,      # 2 min
    _State.COOLDOWN: 15 * 60,  # 15 min
}


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------
class TwitterProvider(ABC):
    """Abstract base for a Twitter data provider."""

    name: str = "base"

    def __init__(self):
        self._available = True
        self._unavailable_until: float = 0

    def is_available(self) -> bool:
        if not self._available and time.time() >= self._unavailable_until:
            self._available = True
        return self._available

    def mark_unavailable(self, cooldown_seconds: int):
        self._available = False
        self._unavailable_until = time.time() + cooldown_seconds
        logger.warning(
            "%s marked unavailable for %ds", self.name, cooldown_seconds
        )

    @abstractmethod
    async def search(self, query: str, limit: int = 50) -> list[dict]:
        """Search tweets, return list of raw tweet dicts."""
        ...

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize provider, return True if ready."""
        ...


# ---------------------------------------------------------------------------
# Provider 1: twscrape (GraphQL API via Twitter account)
# ---------------------------------------------------------------------------
class TwscrapeProvider(TwitterProvider):
    name = "twscrape"

    def __init__(
        self,
        cookies: str = "",
        username: str = "",
        password: str = "",
        email: str = "",
        email_password: str = "",
        db_path: str = "twscrape_accounts.db",
    ):
        super().__init__()
        self._cookies = cookies
        self._username = username
        self._password = password
        self._email = email
        self._email_password = email_password
        self._db_path = db_path
        self._api = None

    async def initialize(self) -> bool:
        try:
            from twscrape import API

            self._api = API(self._db_path)

            # Check if account already exists
            accounts = await self._api.pool.accounts_info()
            if not accounts:
                if self._cookies:
                    await self._api.pool.add_account(
                        self._username or "xingometro",
                        self._password or "unused",
                        self._email or "unused@unused.com",
                        self._email_password or "unused",
                        cookies=self._cookies,
                    )
                    await self._api.pool.login_all()
                    logger.info("twscrape: account added via cookies")
                elif self._username and self._password:
                    await self._api.pool.add_account(
                        self._username,
                        self._password,
                        self._email,
                        self._email_password,
                    )
                    await self._api.pool.login_all()
                    logger.info("twscrape: account added via credentials")
                else:
                    logger.warning("twscrape: no credentials provided")
                    self.mark_unavailable(999_999)
                    return False
            else:
                logger.info("twscrape: using existing account pool")

            return True

        except ImportError:
            logger.warning("twscrape not installed, provider disabled")
            self.mark_unavailable(999_999)
            return False
        except Exception as e:
            logger.error("twscrape init error: %s", e)
            self.mark_unavailable(15 * 60)
            return False

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        if not self._api:
            return []

        try:
            from twscrape import gather as tw_gather

            tweets = await tw_gather(self._api.search(query, limit=limit))
            results = []
            for t in tweets:
                try:
                    results.append(
                        {
                            "external_id": f"tw_{t.id}",
                            "author_handle": f"@{t.user.username}" if t.user else "@unknown",
                            "text": t.rawContent if hasattr(t, "rawContent") else str(t),
                            "created_at": t.date if hasattr(t, "date") else datetime.now(timezone.utc),
                            "source": "twitter",
                        }
                    )
                except Exception as e:
                    logger.debug("twscrape tweet parse error: %s", e)
                    continue

            logger.info("twscrape: fetched %d tweets for query '%s'", len(results), query[:50])
            return results

        except Exception as e:
            error_str = str(e).lower()
            if "no account" in error_str or "locked" in error_str:
                self.mark_unavailable(15 * 60)
            elif "rate" in error_str:
                self.mark_unavailable(15 * 60)
            else:
                self.mark_unavailable(5 * 60)
            logger.error("twscrape search error: %s", e)
            return []


# ---------------------------------------------------------------------------
# Provider 2: ntscraper (via Nitter/xcancel instance)
# ---------------------------------------------------------------------------
class NtscraperProvider(TwitterProvider):
    name = "ntscraper"

    def __init__(self, instance: str = "https://xcancel.com"):
        super().__init__()
        self._instance = instance
        self._scraper = None

    async def initialize(self) -> bool:
        try:
            from ntscraper import Nitter

            # ntscraper is synchronous, instantiate here
            self._scraper = Nitter(
                log_level=0,
                skip_instance_check=True,
            )
            logger.info("ntscraper: initialized with instance %s", self._instance)
            return True

        except ImportError:
            logger.warning("ntscraper not installed, provider disabled")
            self.mark_unavailable(999_999)
            return False
        except Exception as e:
            logger.error("ntscraper init error: %s", e)
            self.mark_unavailable(10 * 60)
            return False

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        if not self._scraper:
            return []

        try:
            # ntscraper is synchronous — run in thread executor
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: self._scraper.get_tweets(
                    query,
                    mode="term",
                    number=limit,
                    instance=self._instance,
                ),
            )

            tweets_list = raw.get("tweets", [])
            results = []
            for t in tweets_list:
                text = t.get("text", "")
                if not text:
                    continue

                # Parse date
                date_str = t.get("date", "")
                try:
                    ts = datetime.strptime(date_str, "%b %d, %Y · %I:%M %p %Z")
                    ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    ts = datetime.now(timezone.utc)

                # Build external_id from link or hash
                link = t.get("link", "")
                tweet_id = link.split("/")[-1] if link else str(hash(text))

                results.append(
                    {
                        "external_id": f"tw_{tweet_id}",
                        "author_handle": t.get("user", {}).get("username", "@unknown"),
                        "text": text,
                        "created_at": ts,
                        "source": "twitter",
                    }
                )

            logger.info("ntscraper: fetched %d tweets for query '%s'", len(results), query[:50])
            return results

        except Exception as e:
            self.mark_unavailable(10 * 60)
            logger.error("ntscraper search error: %s", e)
            return []


# ---------------------------------------------------------------------------
# Provider 3: XCancel direct scraping (httpx + BeautifulSoup)
# ---------------------------------------------------------------------------
class XCancelScraperProvider(TwitterProvider):
    name = "xcancel-scraper"

    def __init__(self, base_url: str = "https://xcancel.com"):
        super().__init__()
        self._base_url = base_url

    async def initialize(self) -> bool:
        try:
            from bs4 import BeautifulSoup  # noqa: F401

            logger.info("xcancel-scraper: initialized (%s)", self._base_url)
            return True
        except ImportError:
            logger.warning("beautifulsoup4 not installed, xcancel-scraper disabled")
            self.mark_unavailable(999_999)
            return False

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        from bs4 import BeautifulSoup

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                follow_redirects=True,
            ) as client:
                url = f"{self._base_url}/search"
                params = {"f": "tweets", "q": query}
                resp = await client.get(url, params=params)

                if resp.status_code == 403:
                    self.mark_unavailable(30 * 60)
                    logger.warning("xcancel-scraper: 403 Forbidden")
                    return []

                if resp.status_code != 200:
                    self.mark_unavailable(10 * 60)
                    logger.warning("xcancel-scraper: HTTP %d", resp.status_code)
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                results = []

                # Nitter/xcancel HTML structure: .timeline-item contains tweets
                tweet_elements = soup.select(".timeline-item")
                if not tweet_elements:
                    # Fallback: try .tweet-content
                    tweet_elements = soup.select(".tweet")

                for elem in tweet_elements[:limit]:
                    # Extract text
                    content_el = elem.select_one(".tweet-content")
                    if not content_el:
                        continue
                    text = content_el.get_text(strip=True)
                    if not text:
                        continue

                    # Extract author
                    author_el = elem.select_one(".username")
                    author = author_el.get_text(strip=True) if author_el else "@unknown"

                    # Extract date
                    date_el = elem.select_one(".tweet-date a")
                    ts = datetime.now(timezone.utc)
                    if date_el:
                        title = date_el.get("title", "")
                        if title:
                            try:
                                ts = datetime.strptime(title, "%b %d, %Y · %I:%M %p %Z")
                                ts = ts.replace(tzinfo=timezone.utc)
                            except (ValueError, TypeError):
                                pass

                    # Extract tweet ID from link
                    link_el = elem.select_one(".tweet-link")
                    if not link_el:
                        link_el = date_el
                    href = link_el.get("href", "") if link_el else ""
                    tweet_id = href.split("/")[-1].replace("#m", "") if href else str(hash(text))

                    results.append(
                        {
                            "external_id": f"tw_{tweet_id}",
                            "author_handle": author,
                            "text": text,
                            "created_at": ts,
                            "source": "twitter",
                        }
                    )

                logger.info(
                    "xcancel-scraper: fetched %d tweets for query '%s'",
                    len(results),
                    query[:50],
                )
                return results

        except httpx.TimeoutException:
            self.mark_unavailable(10 * 60)
            logger.warning("xcancel-scraper: timeout")
            return []
        except Exception as e:
            self.mark_unavailable(30 * 60)
            logger.error("xcancel-scraper error: %s", e)
            return []


# ---------------------------------------------------------------------------
# Query builder: builds search queries from active matches
# ---------------------------------------------------------------------------
def _build_search_queries(team_cache: dict[int, list[str]]) -> list[str]:
    """Build Twitter search queries based on teams with live/upcoming matches."""
    db = SessionLocal()
    try:
        live_matches = (
            db.query(Match)
            .filter(Match.status.in_(["live", "scheduled"]))
            .all()
        )

        if not live_matches:
            # Generic fallback query
            return ['"brasileirão" OR "série a" OR "brasileirao"']

        # Collect team IDs from live matches first, then scheduled
        team_ids: list[int] = []
        for m in live_matches:
            if m.status == "live":
                if m.home_team_id not in team_ids:
                    team_ids.append(m.home_team_id)
                if m.away_team_id not in team_ids:
                    team_ids.append(m.away_team_id)

        # If no live, get scheduled
        if not team_ids:
            for m in live_matches:
                if m.home_team_id not in team_ids:
                    team_ids.append(m.home_team_id)
                if m.away_team_id not in team_ids:
                    team_ids.append(m.away_team_id)

        # Build queries (Twitter search max ~512 chars)
        queries = []
        current_terms: list[str] = []
        current_len = 0

        for tid in team_ids:
            aliases = team_cache.get(tid, [])
            if not aliases:
                continue
            # Pick top 2 aliases (name + popular alias)
            terms = aliases[:2]
            for term in terms:
                quoted = f'"{term}"'
                added_len = len(quoted) + 4  # " OR " separator
                if current_len + added_len > 450 and current_terms:
                    queries.append(" OR ".join(current_terms))
                    current_terms = []
                    current_len = 0
                current_terms.append(quoted)
                current_len += added_len

        if current_terms:
            queries.append(" OR ".join(current_terms))

        return queries if queries else ['"brasileirão" OR "série a"']

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
class TwitterCollector:
    """Collects tweets using a fallback chain of providers."""

    def __init__(
        self,
        on_post: Callable[[dict], None],
        cookies: str = "",
        username: str = "",
        password: str = "",
        email: str = "",
        email_password: str = "",
    ):
        self._on_post = on_post
        self._running = False
        self._state = _State.IDLE
        self._seen_ids: set[str] = set()
        self._team_cache: dict[int, list[str]] = {}

        # Initialize providers in priority order
        self._providers: list[TwitterProvider] = [
            TwscrapeProvider(
                cookies=cookies,
                username=username,
                password=password,
                email=email,
                email_password=email_password,
            ),
            NtscraperProvider(),
            XCancelScraperProvider(),
        ]

    async def start(self):
        """Main polling loop with adaptive intervals."""
        self._running = True
        self._build_team_cache()

        # Initialize all providers
        for provider in self._providers:
            try:
                ok = await provider.initialize()
                logger.info(
                    "Twitter provider '%s' initialized: %s",
                    provider.name,
                    "OK" if ok else "FAILED",
                )
            except Exception as e:
                logger.error("Failed to init provider '%s': %s", provider.name, e)

        logger.info("TwitterCollector started with %d providers", len(self._providers))

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                logger.error("Twitter poll error: %s", e)

            interval = _INTERVALS[self._state]
            logger.debug(
                "Twitter state=%s, next poll in %ds", self._state.value, interval
            )
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False
        logger.info("TwitterCollector stopped")

    async def _poll_cycle(self):
        """One poll: build queries, fetch from best provider, process results."""
        # Refresh team cache periodically
        if not self._team_cache:
            self._build_team_cache()

        queries = _build_search_queries(self._team_cache)
        self._update_state()

        for query in queries:
            if not self._running:
                break

            tweets = await self._fetch_with_fallback(query)
            new_count = 0

            for tweet in tweets:
                ext_id = tweet["external_id"]
                if ext_id in self._seen_ids:
                    continue
                self._seen_ids.add(ext_id)
                new_count += 1
                self._on_post(tweet)

            if new_count > 0:
                logger.info(
                    "Twitter: %d new tweets processed for query '%s'",
                    new_count,
                    query[:60],
                )

        # Prevent unbounded memory growth
        if len(self._seen_ids) > _MAX_SEEN:
            # Keep last 25k
            excess = len(self._seen_ids) - 25_000
            for _ in range(excess):
                self._seen_ids.pop()

    async def _fetch_with_fallback(self, query: str) -> list[dict]:
        """Try each provider in order until one succeeds."""
        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                tweets = await provider.search(query, limit=50)
                if tweets:
                    return tweets
                # Empty result: provider might be working but no data
                logger.debug(
                    "Provider '%s' returned 0 tweets", provider.name
                )
            except Exception as e:
                logger.error(
                    "Provider '%s' failed: %s", provider.name, e
                )
                provider.mark_unavailable(5 * 60)

        logger.debug("All Twitter providers returned no results for: %s", query[:60])
        return []

    def _build_team_cache(self):
        """Build team_id → [aliases] cache."""
        db = SessionLocal()
        try:
            teams = db.query(Team).all()
            for team in teams:
                aliases = [team.name, team.short_name]
                if team.aliases:
                    aliases.extend(team.aliases)
                self._team_cache[team.id] = aliases
        finally:
            db.close()

    def _update_state(self):
        """Update polling state based on current match statuses."""
        from datetime import timedelta

        db = SessionLocal()
        try:
            matches = db.query(Match).filter(
                Match.status.in_(["live", "scheduled", "finished"])
            ).all()

            now = datetime.now(timezone.utc)
            has_live = False
            has_upcoming_soon = False
            has_recently_finished = False

            for m in matches:
                if m.status == "live":
                    has_live = True
                elif m.status == "scheduled" and m.started_at:
                    # Ensure timezone-aware comparison
                    started = m.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    if started - now < timedelta(hours=1):
                        has_upcoming_soon = True
                elif m.status == "finished" and m.finished_at:
                    finished = m.finished_at
                    if finished.tzinfo is None:
                        finished = finished.replace(tzinfo=timezone.utc)
                    if now - finished < timedelta(hours=1):
                        has_recently_finished = True

            if has_live:
                self._state = _State.LIVE
            elif has_upcoming_soon:
                self._state = _State.WARMUP
            elif has_recently_finished:
                self._state = _State.COOLDOWN
            else:
                self._state = _State.IDLE
        finally:
            db.close()
