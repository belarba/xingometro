"""Collector that syncs Brasileirão match data from football-data.org v4."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from unidecode import unidecode

from backend.models.database import SessionLocal
from backend.models.coach import Coach, CoachAssignment
from backend.models.match import Match
from backend.models.team import Team

logger = logging.getLogger(__name__)

# football-data.org status → local status
_STATUS_MAP = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",        # half-time
    "FINISHED": "finished",
    "SUSPENDED": "postponed",
    "POSTPONED": "postponed",
    "CANCELLED": "postponed",
    "AWARDED": "finished",
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
    def __init__(self, api_key: str, competition: str, base_url: str):
        self._api_key = api_key
        self._competition = competition
        self._base_url = base_url
        self._running = False
        self._state = _State.IDLE
        self._current_matchday: Optional[int] = None
        self._current_season: Optional[int] = None
        # Cache team name → id mapping
        self._team_cache: dict = {}
        self._last_coach_sync: Optional[datetime] = None
        self._COACH_SYNC_INTERVAL = timedelta(hours=12)

    async def start(self):
        """Main polling loop with adaptive intervals."""
        self._running = True
        logger.info(
            "FootballAPICollector started (competition=%s)", self._competition
        )

        # Initial coach sync on startup
        try:
            await self.sync_coaches_from_teams()
        except Exception as e:
            logger.error("Initial coach sync failed: %s", e)

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                logger.error("Football API poll error: %s", e)

            interval = _INTERVALS[self._state]
            logger.debug(
                "Football API state=%s, next poll in %ds",
                self._state.value,
                interval,
            )
            await asyncio.sleep(interval)

    async def stop(self):
        """Stop the polling loop."""
        self._running = False
        logger.info("FootballAPICollector stopped")

    async def _poll_cycle(self):
        """One poll cycle: fetch matches from API, sync to DB."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get current matchday if we don't have it
            if self._current_matchday is None:
                self._current_matchday = await self._fetch_current_matchday(
                    client
                )
                if self._current_matchday is None:
                    logger.warning("Could not determine current matchday")
                    return

            # Fetch matches for the matchday
            matches = await self._fetch_matches(client, self._current_matchday)
            if matches is None:
                return

            # Sync to database
            db = SessionLocal()
            try:
                self._sync_matches(matches, db)
                coaches_changed = self._sync_coaches(
                    matches, self._current_matchday, db
                )
                db.commit()
                logger.info(
                    "Synced %d matches (state=%s, matchday=%d)",
                    len(matches),
                    self._state.value,
                    self._current_matchday,
                )
                if coaches_changed:
                    from backend.analyzer.target_detector import target_detector
                    target_detector.reload()
                    logger.info("Reloaded target detector after coach changes")
            except Exception as e:
                db.rollback()
                logger.error("Error syncing matches: %s", e)
            finally:
                db.close()

            # Update state based on match statuses
            self._update_state(matches)

        # Periodic coach sync (every 12h, only in IDLE/COOLDOWN)
        if self._state in (_State.IDLE, _State.COOLDOWN) and self._should_sync_coaches():
            try:
                await self.sync_coaches_from_teams()
            except Exception as e:
                logger.error("Periodic coach sync failed: %s", e)

    async def _api_request(
        self, client: httpx.AsyncClient, endpoint: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        """Make an API request with retry on transient errors."""
        url = f"{self._base_url}/{endpoint}"
        headers = {"X-Auth-Token": self._api_key}

        for attempt in range(2):
            try:
                resp = await client.get(
                    url, headers=headers, params=params or {}
                )

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    logger.warning(
                        "football-data.org rate limited, retry in %ds",
                        retry_after,
                    )
                    if attempt == 0:
                        await asyncio.sleep(min(retry_after, 120))
                        continue
                    return None

                if resp.status_code in (500, 502, 503):
                    if attempt == 0:
                        logger.warning(
                            "football-data.org %d, retrying in 5s...",
                            resp.status_code,
                        )
                        await asyncio.sleep(5)
                        continue
                    logger.error(
                        "football-data.org %d after retry", resp.status_code
                    )
                    return None

                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException:
                if attempt == 0:
                    logger.warning("football-data.org timeout, retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                logger.error("football-data.org timeout after retry")
                return None
            except httpx.HTTPError as e:
                logger.error("football-data.org HTTP error: %s", e)
                return None

        return None

    async def _fetch_current_matchday(
        self, client: httpx.AsyncClient
    ) -> Optional[int]:
        """Fetch current matchday from competition info."""
        data = await self._api_request(
            client, f"competitions/{self._competition}"
        )
        if not data:
            return None

        season = data.get("currentSeason", {})
        matchday = season.get("currentMatchday")

        # Extract season year from startDate (e.g. "2025-04-01")
        start_date = season.get("startDate", "")
        if start_date and len(start_date) >= 4:
            try:
                self._current_season = int(start_date[:4])
            except ValueError:
                pass
        if self._current_season is None:
            self._current_season = datetime.now(timezone.utc).year

        if matchday is not None:
            return int(matchday)
        return None

    async def _fetch_matches(
        self, client: httpx.AsyncClient, matchday: int
    ) -> Optional[list]:
        """Fetch all matches for a given matchday."""
        data = await self._api_request(
            client,
            f"competitions/{self._competition}/matches",
            {"matchday": matchday},
        )
        if not data:
            return None
        return data.get("matches", [])

    def _sync_matches(self, matches: list, db: Session):
        """Create or update Match records from API matches."""
        if not self._team_cache:
            self._build_team_cache(db)

        for m in matches:
            ext_id = str(m.get("id", ""))
            if not ext_id:
                continue

            # Resolve teams
            home_name = m.get("homeTeam", {}).get("name", "")
            away_name = m.get("awayTeam", {}).get("name", "")
            home_team_id = self._resolve_team(home_name)
            away_team_id = self._resolve_team(away_name)

            if not home_team_id or not away_team_id:
                logger.warning(
                    "Could not resolve teams: %s vs %s", home_name, away_name
                )
                continue

            matchday = m.get("matchday", 0)

            # Map status
            api_status = m.get("status", "SCHEDULED")
            local_status = _STATUS_MAP.get(api_status, "scheduled")

            # Parse utcDate
            started_at = None
            date_str = m.get("utcDate")
            if date_str:
                try:
                    started_at = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            # Scores
            score = m.get("score", {})
            full_time = score.get("fullTime", {})
            home_score = full_time.get("home") or 0
            away_score = full_time.get("away") or 0

            # Map events (goals + bookings)
            mapped_events = self._map_events(m)

            # Find or create match
            match = (
                db.query(Match).filter(Match.external_id == ext_id).first()
            )

            if match is None:
                match = Match(
                    external_id=ext_id,
                    round=matchday,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=home_score,
                    away_score=away_score,
                    status=local_status,
                    events=mapped_events,
                    started_at=started_at,
                )
                db.add(match)
            else:
                match.home_score = home_score
                match.away_score = away_score
                match.events = mapped_events

                if match.status != local_status:
                    if local_status == "finished" and match.status == "live":
                        match.finished_at = datetime.now(timezone.utc)
                    match.status = local_status

                if started_at and not match.started_at:
                    match.started_at = started_at

    def _map_events(self, match_data: dict) -> list:
        """Map football-data.org goals and bookings to our event format."""
        mapped = []

        # Goals
        for goal in match_data.get("goals", []):
            team_name = goal.get("team", {}).get("name", "")
            team_id = self._resolve_team(team_name)
            mapped.append(
                {
                    "type": "goal",
                    "team_id": team_id,
                    "player": goal.get("scorer", {}).get("name", ""),
                    "minute": goal.get("minute", 0),
                    "detail": goal.get("type", ""),
                }
            )

        # Bookings (yellow/red cards)
        for booking in match_data.get("bookings", []):
            team_name = booking.get("team", {}).get("name", "")
            team_id = self._resolve_team(team_name)
            card_type = booking.get("card", "")
            mapped.append(
                {
                    "type": "red_card" if "RED" in card_type.upper() else "yellow_card",
                    "team_id": team_id,
                    "player": booking.get("player", {}).get("name", ""),
                    "minute": booking.get("minute", 0),
                    "detail": card_type,
                }
            )

        # Substitutions
        for sub in match_data.get("substitutions", []):
            team_name = sub.get("team", {}).get("name", "")
            team_id = self._resolve_team(team_name)
            mapped.append(
                {
                    "type": "substitution",
                    "team_id": team_id,
                    "player": sub.get("playerIn", {}).get("name", ""),
                    "minute": sub.get("minute", 0),
                    "detail": f"out: {sub.get('playerOut', {}).get('name', '')}",
                }
            )

        return mapped

    def _sync_coaches(self, matches: list, matchday: int, db: Session) -> bool:
        """Extract coach data from match responses and sync to DB.

        Returns True if any coach data changed.
        """
        season = self._current_season or datetime.now(timezone.utc).year
        changed = False

        for m in matches:
            for side in ("homeTeam", "awayTeam"):
                team_data = m.get(side, {})
                coach_data = team_data.get("coach")
                if not coach_data or not coach_data.get("id"):
                    continue

                team_name = team_data.get("name", "")
                team_id = self._resolve_team(team_name)
                if not team_id:
                    continue

                api_coach_id = str(coach_data["id"])
                coach_name = coach_data.get("name", "").strip()
                if not coach_name:
                    continue

                coach = self._resolve_or_create_coach(
                    api_coach_id, coach_name, team_id, db
                )
                if not coach:
                    continue

                # Update Coach.team_id to latest assignment
                if coach.team_id != team_id:
                    coach.team_id = team_id
                    changed = True

                # Upsert CoachAssignment
                assignment = (
                    db.query(CoachAssignment)
                    .filter(
                        CoachAssignment.coach_id == coach.id,
                        CoachAssignment.round == matchday,
                        CoachAssignment.season == season,
                    )
                    .first()
                )
                if assignment is None:
                    db.add(CoachAssignment(
                        coach_id=coach.id,
                        team_id=team_id,
                        round=matchday,
                        season=season,
                    ))
                    changed = True
                elif assignment.team_id != team_id:
                    assignment.team_id = team_id
                    changed = True

        return changed

    def _resolve_or_create_coach(
        self, api_coach_id: str, name: str, team_id: int, db: Session
    ) -> Optional[Coach]:
        """Find existing coach by external_id or name match, or create new."""
        # 1. Match by external_id
        coach = (
            db.query(Coach).filter(Coach.external_id == api_coach_id).first()
        )
        if coach:
            if coach.name != name:
                coach.name = name
            return coach

        # 2. Match seed coaches by normalized name + team
        normalized_api = unidecode(name).lower().strip()
        candidates = db.query(Coach).filter(
            Coach.external_id.is_(None),
            Coach.team_id == team_id,
        ).all()
        for c in candidates:
            normalized_db = unidecode(c.name).lower().strip()
            if normalized_db == normalized_api or normalized_db in normalized_api or normalized_api in normalized_db:
                c.external_id = api_coach_id
                c.name = name
                return c

        # 3. Create new coach
        coach = Coach(
            name=name,
            aliases=[],
            team_id=team_id,
            external_id=api_coach_id,
        )
        db.add(coach)
        db.flush()
        return coach

    async def sync_coaches_from_teams(self):
        """Fetch all teams from competition and sync coach data.

        Calls GET /competitions/{id}/teams which returns every team
        with its current coach. Handles coach=null (team without coach).
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            data = await self._api_request(
                client, f"competitions/{self._competition}/teams"
            )
        if not data:
            logger.warning("Could not fetch teams for coach sync")
            return

        teams_data = data.get("teams", [])
        if not teams_data:
            return

        db = SessionLocal()
        try:
            if not self._team_cache:
                self._build_team_cache(db)

            changed = False
            for team_data in teams_data:
                team_name = team_data.get("name", "")
                team_id = self._resolve_team(team_name)
                if not team_id:
                    continue

                coach_data = team_data.get("coach")
                if not coach_data or not coach_data.get("id"):
                    # Team has no coach (e.g. fired, not yet replaced)
                    logger.info(
                        "No coach for team %s (id=%d)", team_name, team_id
                    )
                    continue

                api_coach_id = str(coach_data["id"])
                coach_name = coach_data.get("name", "").strip()
                if not coach_name:
                    continue

                coach = self._resolve_or_create_coach(
                    api_coach_id, coach_name, team_id, db
                )
                if not coach:
                    continue

                if coach.team_id != team_id:
                    logger.info(
                        "Coach %s transferred: team %d → %d",
                        coach_name, coach.team_id, team_id,
                    )
                    coach.team_id = team_id
                    changed = True

                # Check if name was updated by _resolve_or_create_coach
                if db.is_modified(coach):
                    changed = True

            db.commit()
            self._last_coach_sync = datetime.now(timezone.utc)
            logger.info(
                "Coach sync complete: %d teams processed", len(teams_data)
            )

            if changed:
                from backend.analyzer.target_detector import target_detector
                target_detector.reload()
                logger.info("Reloaded target detector after coach sync")

        except Exception as e:
            db.rollback()
            logger.error("Error in coach sync: %s", e)
        finally:
            db.close()

    def _should_sync_coaches(self) -> bool:
        """Check if enough time has passed since last coach sync."""
        if self._last_coach_sync is None:
            return True
        return datetime.now(timezone.utc) - self._last_coach_sync > self._COACH_SYNC_INTERVAL

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

    def _update_state(self, matches: list):
        """Update polling state based on match statuses."""
        statuses = set()
        has_upcoming_soon = False
        now = datetime.now(timezone.utc)

        for m in matches:
            api_status = m.get("status", "SCHEDULED")
            local_status = _STATUS_MAP.get(api_status, "scheduled")
            statuses.add(local_status)

            if local_status == "scheduled":
                date_str = m.get("utcDate")
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
            if "scheduled" in statuses:
                self._state = _State.COOLDOWN
            elif self._state in (_State.LIVE, _State.COOLDOWN):
                self._state = _State.COOLDOWN
            else:
                self._state = _State.IDLE
        elif self._state == _State.COOLDOWN and "scheduled" not in statuses:
            self._state = _State.IDLE
        else:
            self._state = _State.IDLE
