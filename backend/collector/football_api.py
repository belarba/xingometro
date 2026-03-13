"""Collector that syncs Brasileirão match data from API-Football v3."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.models.match import Match
from backend.models.team import Team

logger = logging.getLogger(__name__)

# API-Football status → local status
_STATUS_MAP = {
    "TBD": "scheduled",
    "NS": "scheduled",
    "1H": "live",
    "HT": "live",
    "2H": "live",
    "ET": "live",
    "BT": "live",
    "P": "live",
    "FT": "finished",
    "AET": "finished",
    "PEN": "finished",
    "PST": "postponed",
    "CANC": "postponed",
    "ABD": "postponed",
    "WO": "postponed",
}

# API-Football event type → local event type
_EVENT_TYPE_MAP = {
    "Goal": "goal",
    "Card": "card",
    "subst": "substitution",
}


class _State(Enum):
    IDLE = "idle"
    WARMUP = "warmup"
    LIVE = "live"
    COOLDOWN = "cooldown"


_INTERVALS = {
    _State.IDLE: 60 * 60,      # 60 min
    _State.WARMUP: 10 * 60,    # 10 min
    _State.LIVE: 2 * 60,       # 2 min
    _State.COOLDOWN: 30 * 60,  # 30 min
}


class FootballAPICollector:
    def __init__(self, api_key: str, league_id: int, season: int, base_url: str):
        self._api_key = api_key
        self._league_id = league_id
        self._season = season
        self._base_url = base_url
        self._running = False
        self._state = _State.IDLE
        self._current_round: Optional[str] = None
        self._remaining_requests: Optional[int] = None
        # Cache team name → id mapping
        self._team_cache: dict = {}

    async def start(self):
        """Main polling loop with adaptive intervals."""
        self._running = True
        logger.info(
            "FootballAPICollector started (league=%s, season=%s)",
            self._league_id,
            self._season,
        )

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                logger.error("Football API poll error: %s", e)

            interval = self._determine_interval()
            logger.debug(
                "Football API state=%s, next poll in %ds", self._state.value, interval
            )
            await asyncio.sleep(interval)

    async def stop(self):
        """Stop the polling loop."""
        self._running = False
        logger.info("FootballAPICollector stopped")

    async def _poll_cycle(self):
        """One poll cycle: fetch data from API, sync to DB."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get current round if we don't have it
            if self._current_round is None:
                self._current_round = await self._fetch_current_round(client)
                if self._current_round is None:
                    logger.warning("Could not determine current round")
                    return

            # Fetch fixtures for the round
            fixtures = await self._fetch_fixtures(client, self._current_round)
            if fixtures is None:
                return

            # Sync to database
            db = SessionLocal()
            try:
                self._sync_matches(fixtures, db)
                db.commit()
                logger.info(
                    "Synced %d fixtures (state=%s)", len(fixtures), self._state.value
                )
            except Exception as e:
                db.rollback()
                logger.error("Error syncing matches: %s", e)
            finally:
                db.close()

            # Update state based on fixture statuses
            self._update_state(fixtures)

    async def _api_request(
        self, client: httpx.AsyncClient, endpoint: str, params: dict
    ) -> Optional[dict]:
        """Make an API request with retry on transient errors."""
        url = f"{self._base_url}/{endpoint}"
        headers = {
            "x-apisports-key": self._api_key,
        }

        for attempt in range(2):
            try:
                resp = await client.get(url, headers=headers, params=params)

                # Track rate limit
                remaining = resp.headers.get("x-ratelimit-requests-remaining")
                if remaining is not None:
                    self._remaining_requests = int(remaining)
                    if self._remaining_requests < 10:
                        logger.warning(
                            "API-Football rate limit low: %d remaining",
                            self._remaining_requests,
                        )

                if resp.status_code in (429, 500, 502, 503):
                    if attempt == 0:
                        logger.warning(
                            "API-Football %d, retrying in 5s...", resp.status_code
                        )
                        await asyncio.sleep(5)
                        continue
                    logger.error("API-Football %d after retry", resp.status_code)
                    return None

                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException:
                if attempt == 0:
                    logger.warning("API-Football timeout, retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                logger.error("API-Football timeout after retry")
                return None
            except httpx.HTTPError as e:
                logger.error("API-Football HTTP error: %s", e)
                return None

        return None

    async def _fetch_current_round(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch the current round string (e.g., 'Regular Season - 12')."""
        data = await self._api_request(
            client,
            "fixtures/rounds",
            {
                "league": self._league_id,
                "season": self._season,
                "current": "true",
            },
        )
        if not data or not data.get("response"):
            return None
        # Returns list like ["Regular Season - 12"]
        return data["response"][0]

    async def _fetch_fixtures(
        self, client: httpx.AsyncClient, round_str: str
    ) -> Optional[list]:
        """Fetch all fixtures for a given round."""
        data = await self._api_request(
            client,
            "fixtures",
            {
                "league": self._league_id,
                "season": self._season,
                "round": round_str,
            },
        )
        if not data:
            return None
        return data.get("response", [])

    def _sync_matches(self, fixtures: list, db: Session):
        """Create or update Match records from API fixtures."""
        if not self._team_cache:
            self._build_team_cache(db)

        for fx in fixtures:
            fixture_data = fx.get("fixture", {})
            teams_data = fx.get("teams", {})
            goals_data = fx.get("goals", {})
            events_data = fx.get("events", [])

            ext_id = str(fixture_data.get("id", ""))
            if not ext_id:
                continue

            # Resolve teams
            home_name = teams_data.get("home", {}).get("name", "")
            away_name = teams_data.get("away", {}).get("name", "")
            home_team_id = self._resolve_team(home_name)
            away_team_id = self._resolve_team(away_name)

            if not home_team_id or not away_team_id:
                logger.warning(
                    "Could not resolve teams: %s vs %s", home_name, away_name
                )
                continue

            # Parse round number
            round_str = fx.get("league", {}).get("round", "")
            round_num = self._parse_round(round_str)

            # Map status
            api_status = fixture_data.get("status", {}).get("short", "NS")
            local_status = _STATUS_MAP.get(api_status, "scheduled")

            # Parse started_at
            started_at = None
            date_str = fixture_data.get("date")
            if date_str:
                try:
                    started_at = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            # Map events
            mapped_events = self._map_events(events_data)

            # Find or create match
            match = (
                db.query(Match).filter(Match.external_id == ext_id).first()
            )

            if match is None:
                match = Match(
                    external_id=ext_id,
                    round=round_num,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=goals_data.get("home") or 0,
                    away_score=goals_data.get("away") or 0,
                    status=local_status,
                    events=mapped_events,
                    started_at=started_at,
                )
                db.add(match)
            else:
                # Update existing
                match.home_score = goals_data.get("home") or 0
                match.away_score = goals_data.get("away") or 0
                match.events = mapped_events

                # Track status transitions
                if match.status != local_status:
                    if local_status == "finished" and match.status == "live":
                        match.finished_at = datetime.now(timezone.utc)
                    match.status = local_status

                if started_at and not match.started_at:
                    match.started_at = started_at

    def _map_events(self, events_data: list) -> list:
        """Map API-Football events to our event format."""
        mapped = []
        for evt in events_data:
            evt_type = evt.get("type", "")
            local_type = _EVENT_TYPE_MAP.get(evt_type)
            if not local_type:
                continue

            # Refine card type
            if local_type == "card":
                detail = evt.get("detail", "")
                if "Red" in detail:
                    local_type = "red_card"
                else:
                    local_type = "yellow_card"

            team_name = evt.get("team", {}).get("name", "")
            team_id = self._resolve_team(team_name)

            mapped.append(
                {
                    "type": local_type,
                    "team_id": team_id,
                    "player": evt.get("player", {}).get("name", ""),
                    "minute": evt.get("time", {}).get("elapsed", 0),
                    "detail": evt.get("detail", ""),
                }
            )
        return mapped

    def _build_team_cache(self, db: Session):
        """Build name → id cache from all teams."""
        teams = db.query(Team).all()
        for team in teams:
            self._team_cache[team.name.lower()] = team.id
            self._team_cache[team.short_name.lower()] = team.id
            if team.aliases:
                for alias in team.aliases:
                    self._team_cache[alias.lower()] = team.id

    def _resolve_team(self, api_name: str) -> Optional[int]:
        """Resolve API team name to local team ID."""
        if not api_name:
            return None

        name_lower = api_name.lower()

        # Exact match
        if name_lower in self._team_cache:
            return self._team_cache[name_lower]

        # Substring match
        for cached_name, team_id in self._team_cache.items():
            if cached_name in name_lower or name_lower in cached_name:
                return team_id

        logger.warning("Could not resolve team: %s", api_name)
        return None

    @staticmethod
    def _parse_round(round_str: str) -> int:
        """Parse 'Regular Season - 12' → 12."""
        match = re.search(r"(\d+)", round_str)
        return int(match.group(1)) if match else 0

    def _update_state(self, fixtures: list):
        """Update polling state based on fixture statuses."""
        statuses = set()
        has_upcoming_soon = False
        now = datetime.now(timezone.utc)

        for fx in fixtures:
            fixture_data = fx.get("fixture", {})
            api_status = fixture_data.get("status", {}).get("short", "NS")
            local_status = _STATUS_MAP.get(api_status, "scheduled")
            statuses.add(local_status)

            # Check if any scheduled match starts within 1 hour
            if local_status == "scheduled":
                date_str = fixture_data.get("date")
                if date_str:
                    try:
                        start = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                        if start - now < timedelta(hours=1):
                            has_upcoming_soon = True
                    except (ValueError, TypeError):
                        pass

        if "live" in statuses:
            self._state = _State.LIVE
        elif has_upcoming_soon:
            self._state = _State.WARMUP
        elif "finished" in statuses and "live" not in statuses:
            # Some matches finished. May still have scheduled matches in
            # multi-day rounds (Fri-Mon). Stay in COOLDOWN to keep checking.
            if "scheduled" in statuses:
                self._state = _State.COOLDOWN
            elif self._state in (_State.LIVE, _State.COOLDOWN):
                self._state = _State.COOLDOWN
            else:
                self._state = _State.IDLE
        elif self._state == _State.COOLDOWN and "scheduled" not in statuses:
            self._state = _State.IDLE
        elif "scheduled" in statuses:
            self._state = _State.IDLE
        else:
            self._state = _State.IDLE

    def _determine_interval(self) -> int:
        """Return seconds until next poll. Respect rate limits."""
        if self._remaining_requests is not None and self._remaining_requests < 10:
            return 30 * 60  # 30 min safety fallback

        return _INTERVALS[self._state]
