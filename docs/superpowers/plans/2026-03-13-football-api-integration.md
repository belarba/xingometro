# Football API Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate API-Football v3 to automatically sync Brasileirão match data (fixtures, scores, events) replacing static JSON seeds.

**Architecture:** A new `FootballAPICollector` class follows the same async collector pattern as `JetstreamCollector`. It runs as a background task in FastAPI's lifespan, polling API-Football with adaptive intervals based on match state (IDLE/WARMUP/LIVE/COOLDOWN). Uses `httpx.AsyncClient` for HTTP and `SessionLocal()` per poll cycle for DB access.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy, httpx (already installed), python-dotenv (new)

**Spec:** `docs/superpowers/specs/2026-03-13-football-api-integration-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/config.py` | Modify | Add dotenv loading, API-Football config vars |
| `backend/models/match.py` | Modify | Add `external_id` column |
| `backend/collector/football_api.py` | Create | FootballAPICollector class with adaptive polling |
| `backend/main.py` | Modify | Wire football collector into lifespan |
| `backend/requirements.txt` | Modify | Add python-dotenv |
| `.env` | Create | FOOTBALL_API_KEY placeholder |
| `.env.example` | Create | Template for env vars |

---

## Chunk 1: Foundation (config, model, dependencies)

### Task 1: Add python-dotenv dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add python-dotenv to requirements.txt**

Add at the end of `backend/requirements.txt`:
```
python-dotenv==1.0.1
```

- [ ] **Step 2: Install the dependency**

Run: `cd /Users/danielbelarmino/code/estudos/xingometro-times && pip install python-dotenv==1.0.1`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add python-dotenv for env var loading"
```

---

### Task 2: Update config.py with API-Football settings

**Files:**
- Modify: `backend/config.py`
- Create: `.env`
- Create: `.env.example`

- [ ] **Step 1: Update config.py**

Replace the entire `backend/config.py` with:

```python
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "xingometro.db"

JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe"

# Termos para filtrar posts relevantes do firehose
FOOTBALL_TERMS = [
    "brasileirão", "brasileirao", "serie a", "série a",
    "futebol", "gol", "jogo", "rodada", "campeonato",
    "arbitro", "árbitro", "juiz", "var",
    "escalação", "escalacao", "titular", "reserva",
]

# Intervalo em segundos para atualizar rage_snapshots
SNAPSHOT_INTERVAL = 30

# Máximo de posts no feed SSE (buffer)
SSE_BUFFER_SIZE = 50

# CORS
FRONTEND_URL = "http://localhost:5173"

# API-Football
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"
FOOTBALL_LEAGUE_ID = 71  # Brasileirão Série A
FOOTBALL_SEASON = int(os.environ.get("FOOTBALL_SEASON", str(datetime.now().year)))
```

- [ ] **Step 2: Create .env file**

Create `.env` in project root:
```
FOOTBALL_API_KEY=
```

- [ ] **Step 3: Create .env.example file**

Create `.env.example` in project root:
```
# API-Football key (get free at https://www.api-football.com/)
FOOTBALL_API_KEY=your_key_here

# Optional: override season year (defaults to current year)
# FOOTBALL_SEASON=2026
```

- [ ] **Step 4: Verify .env is in .gitignore**

Check that `.env` is already in `.gitignore` (it is — line 7). `.env.example` should NOT be in `.gitignore`.

- [ ] **Step 5: Verify backend still starts**

Run: `cd /Users/danielbelarmino/code/estudos/xingometro-times && python -c "from backend.config import FOOTBALL_API_KEY, FOOTBALL_SEASON; print(f'Key: {bool(FOOTBALL_API_KEY)}, Season: {FOOTBALL_SEASON}')"`

Expected: `Key: False, Season: 2026`

- [ ] **Step 6: Commit**

```bash
git add backend/config.py .env.example
git commit -m "config: add API-Football settings with dotenv loading"
```

---

### Task 3: Add external_id to Match model

**Files:**
- Modify: `backend/models/match.py`

- [ ] **Step 1: Add external_id field to Match**

Add after the `id` line in `backend/models/match.py`:
```python
external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
```

The full model should look like:
```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.database import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    home_score: Mapped[int] = mapped_column(Integer, default=0)
    away_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, default="scheduled")
    events: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: Delete old SQLite DB to recreate schema**

Run: `rm -f /Users/danielbelarmino/code/estudos/xingometro-times/backend/xingometro.db`

The DB will be recreated on next server start via `init_db()` → `Base.metadata.create_all()`.

- [ ] **Step 3: Verify model loads**

Run: `cd /Users/danielbelarmino/code/estudos/xingometro-times && python -c "from backend.models.match import Match; print(Match.__table__.columns.keys())"`

Expected output should include `external_id` in the list.

- [ ] **Step 4: Commit**

```bash
git add backend/models/match.py
git commit -m "model: add external_id to Match for API-Football dedup"
```

---

## Chunk 2: FootballAPICollector implementation

### Task 4: Create the FootballAPICollector class

**Files:**
- Create: `backend/collector/football_api.py`

This is the main implementation. The collector follows the same pattern as `JetstreamCollector`:
- `__init__` sets up config
- `async start()` is the main polling loop
- `async stop()` for graceful shutdown

- [ ] **Step 1: Create backend/collector/football_api.py**

```python
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
_STATUS_MAP: dict[str, str] = {
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
_EVENT_TYPE_MAP: dict[str, str] = {
    "Goal": "goal",
    "Card": "card",
    "subst": "substitution",
}


class _State(Enum):
    IDLE = "idle"
    WARMUP = "warmup"
    LIVE = "live"
    COOLDOWN = "cooldown"


_INTERVALS: dict[_State, int] = {
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
        self._team_cache: dict[str, int] = {}

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
    ) -> Optional[list[dict]]:
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

    def _sync_matches(self, fixtures: list[dict], db: Session):
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

    def _map_events(self, events_data: list[dict]) -> list[dict]:
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
            # Index by name, short_name, and aliases
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

    def _update_state(self, fixtures: list[dict]):
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
                # Still have upcoming matches in this round
                self._state = _State.COOLDOWN
            elif self._state in (_State.LIVE, _State.COOLDOWN):
                # All matches done, transition through cooldown
                self._state = _State.COOLDOWN
            else:
                self._state = _State.IDLE
        elif self._state == _State.COOLDOWN and "scheduled" not in statuses:
            # Cooldown complete, no more matches
            self._state = _State.IDLE
        elif "scheduled" in statuses:
            # Only scheduled matches, no urgency
            self._state = _State.IDLE
        else:
            self._state = _State.IDLE

    def _determine_interval(self) -> int:
        """Return seconds until next poll. Respect rate limits."""
        if self._remaining_requests is not None and self._remaining_requests < 10:
            return 30 * 60  # 30 min safety fallback

        return _INTERVALS[self._state]
```

- [ ] **Step 2: Verify the module imports correctly**

Run: `cd /Users/danielbelarmino/code/estudos/xingometro-times && python -c "from backend.collector.football_api import FootballAPICollector; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/collector/football_api.py
git commit -m "feat: add FootballAPICollector with adaptive polling"
```

---

## Chunk 3: Wire into main.py and finalize

### Task 5: Wire FootballAPICollector into FastAPI lifespan

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add imports to main.py**

At the top of `backend/main.py`, add after the existing imports:

```python
from backend.config import FOOTBALL_API_KEY, FOOTBALL_API_BASE, FOOTBALL_LEAGUE_ID, FOOTBALL_SEASON
from backend.collector.football_api import FootballAPICollector
```

- [ ] **Step 2: Update the lifespan function**

Replace the `lifespan` function in `backend/main.py` with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _load_seed_data()

    collector_task = asyncio.create_task(collector.start())
    set_connected(True)
    snapshot_task = asyncio.create_task(_snapshot_loop())

    # Football API collector (optional, needs API key)
    football_collector = None
    football_task = None
    if FOOTBALL_API_KEY:
        football_collector = FootballAPICollector(
            api_key=FOOTBALL_API_KEY,
            league_id=FOOTBALL_LEAGUE_ID,
            season=FOOTBALL_SEASON,
            base_url=FOOTBALL_API_BASE,
        )
        football_task = asyncio.create_task(football_collector.start())
        logger.info("Football API collector started (league=%s)", FOOTBALL_LEAGUE_ID)
    else:
        logger.info("No FOOTBALL_API_KEY set — using seed data only")

    logger.info("Xingômetro started! Collecting from Bluesky Jetstream...")
    yield

    set_connected(False)
    await collector.stop()
    snapshot_task.cancel()
    collector_task.cancel()

    if football_collector:
        await football_collector.stop()
    if football_task:
        football_task.cancel()
```

- [ ] **Step 3: Verify backend starts without API key**

Delete the DB and restart:
```bash
rm -f /Users/danielbelarmino/code/estudos/xingometro-times/backend/xingometro.db
```

Then start the backend and check logs for: `No FOOTBALL_API_KEY set — using seed data only`

- [ ] **Step 4: Verify backend starts with API key**

Add the real API key to `.env`:
```
FOOTBALL_API_KEY=your_actual_key
```

Restart the backend and check logs for: `Football API collector started (league=71)`

- [ ] **Step 5: Verify API calls work**

With the API key set, check backend logs for one of:
- `Synced X fixtures (state=idle)` — success, fixtures loaded
- `Could not determine current round` — API returned empty (off-season or wrong league ID)
- `API-Football 4XX` — authentication issue (check key)

If the Brasileirão is off-season, the round endpoint may return empty. This is expected — the collector gracefully handles it by retrying on next interval.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py
git commit -m "feat: wire FootballAPICollector into FastAPI lifespan"
```

---

### Task 6: Run seed_demo and verify dashboard still works

**Files:** None (verification only)

- [ ] **Step 1: Run seed_demo to populate test data**

```bash
cd /Users/danielbelarmino/code/estudos/xingometro-times && python -m backend.seed_demo
```

Expected: `✅ X posts de demo criados!`

- [ ] **Step 2: Restart backend server**

Stop and restart the backend preview server.

- [ ] **Step 3: Verify all API endpoints**

```bash
curl -s http://localhost:8000/api/rankings | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} teams')"
curl -s http://localhost:8000/api/matches | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} matches')"
curl -s http://localhost:8000/api/rankings/coaches | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} coaches')"
```

Expected: Non-zero counts for all three.

- [ ] **Step 4: Check dashboard in browser**

Take a screenshot to verify the dashboard shows rankings, word cloud, and timeline.

- [ ] **Step 5: Final commit with all remaining changes**

```bash
git add -A
git commit -m "feat: complete API-Football integration for automatic match sync

- FootballAPICollector with adaptive polling (IDLE/WARMUP/LIVE/COOLDOWN)
- Match.external_id for API-Football fixture dedup
- Config via .env with python-dotenv
- Graceful fallback when no API key is set
- Rate limit tracking and retry on transient errors"
```
