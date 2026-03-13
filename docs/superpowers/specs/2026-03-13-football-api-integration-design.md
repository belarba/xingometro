# Football API Integration — Design Spec

## Overview

Integrate API-Football v3 to automatically sync Brasileirão match data (fixtures, scores, events) into the Xingometro system, replacing the static JSON seed for matches.

## Data Source

- **Provider:** API-Football (api-sports.io)
- **Version:** v3
- **Base URL:** `https://v3.football.api-sports.io`
- **Auth:** Header `x-apisports-key: <key>`
- **League ID:** 71 (Brasileirão Série A)
- **Free tier:** 100 requests/day, 10 requests/minute

## Endpoints Used

### 1. Current Round

```
GET /fixtures/rounds?league=71&season=2026&current=true
→ ["Regular Season - 12"]
```

One request to know which round is active. Parse integer from string.

### 2. Fixtures by Round

```
GET /fixtures?league=71&season=2026&round=Regular Season - 12
→ { response: [{ fixture, league, teams, goals, score, events }] }
```

Returns all 10 matches of the round with current status and scores. Used for initial load and periodic sync.

### 3. Live Fixtures (reserved, not used in current design)

The `/fixtures?live=all&league=71` endpoint exists but we always use fixtures-by-round instead (see "Endpoint Per State" table) to avoid missing matches that start at different times in multi-day rounds.

## Response Mapping

### Fixture → Match

| API-Football | Match model | Notes |
|---|---|---|
| `fixture.id` | `external_id` (new) | String, for dedup |
| `league.round` | `round` | Parse "Regular Season - 12" → 12 |
| `teams.home.name` | `home_team_id` | Fuzzy match against Team.name/aliases |
| `teams.away.name` | `away_team_id` | Fuzzy match against Team.name/aliases |
| `goals.home` | `home_score` | Integer |
| `goals.away` | `away_score` | Integer |
| `fixture.status.short` | `status` | See status mapping below |
| `fixture.date` | `started_at` | ISO datetime |
| `fixture.status.short == FT` | `finished_at` | Set to now() on transition |

### Status Mapping

| API-Football status | Match.status |
|---|---|
| `TBD`, `NS` | `scheduled` |
| `1H`, `HT`, `2H`, `ET`, `BT`, `P` | `live` |
| `FT`, `AET`, `PEN` | `finished` |
| `PST`, `CANC`, `ABD`, `WO` | `postponed` |

### Events → Match.events

Each event from the fixture response maps to:

```json
{
  "type": "goal" | "yellow_card" | "red_card" | "substitution",
  "team_id": <local team id>,
  "player": "Player Name",
  "minute": 45,
  "detail": "Normal Goal" | "Penalty" | "Own Goal"
}
```

API-Football event types: "Goal", "Card", "subst" → mapped to our types.

## Polling Strategy

### Adaptive Intervals

```
State                    Interval    Est. req/day
─────────────────────────────────────────────────
No games today           60 min      ~24
Game starts in <1h       10 min      ~6
Game is live             2 min       ~60 (for 2h)
Post-game cooldown       30 min      ~4
─────────────────────────────────────────────────
Total (match day)                    ~50-70 req
```

### State Machine

```
            ┌──────────┐
    ┌───────│  IDLE     │◄────────────────┐
    │       │ (60 min)  │                 │
    │       └─────┬─────┘                 │
    │             │ game starts in <1h     │
    │             ▼                        │
    │       ┌──────────┐                  │
    │       │ WARMUP   │                  │
    │       │ (10 min)  │                 │
    │       └─────┬─────┘                 │
    │             │ any match.status=live  │
    │             ▼                        │
    │       ┌──────────┐                  │
    │       │  LIVE    │                  │
    │       │ (2 min)   │                 │
    │       └─────┬─────┘                 │
    │             │ all matches finished   │
    │             ▼                        │
    │       ┌──────────┐                  │
    └───────│ COOLDOWN │──────────────────┘
            │ (30 min)  │  after 1 cycle
            └──────────┘
```

### Endpoint Per State

| State | Endpoint | Reason |
|---|---|---|
| IDLE | `/fixtures?league=X&season=Y&round=Z` | Check if any match is approaching |
| WARMUP | `/fixtures?league=X&season=Y&round=Z` | Detect status transitions |
| LIVE | `/fixtures?league=X&season=Y&round=Z` | Full round data (captures newly started matches too) |
| COOLDOWN | `/fixtures?league=X&season=Y&round=Z` | Check for remaining scheduled matches in round |

Always use fixtures-by-round (not live-only) to avoid missing matches that start at different times in the same round. Brasileirão rounds span multiple days (Fri-Mon).

### COOLDOWN Transition

During COOLDOWN, if any fixture in the round still has status `NS` with start time within 1 hour, transition to WARMUP instead of IDLE. This handles rounds spread across multiple days.

### Rate Limit Safety

- Track remaining requests via `x-ratelimit-requests-remaining` response header
- If remaining < 10, fall back to 30 min interval regardless of state
- Log warnings when approaching limit

## New Files

### `backend/collector/football_api.py`

```python
class FootballAPICollector:
    def __init__(self, api_key: str, league_id: int, season: int):
        ...

    async def start(self):
        """Main loop: poll API-Football with adaptive intervals."""

    async def stop(self):
        """Cancel the polling loop."""

    async def _fetch_current_round(self) -> int:
        """GET /fixtures/rounds → parse round number."""

    async def _fetch_fixtures(self, round_str: str) -> list[dict]:
        """GET /fixtures?league=X&season=Y&round=Z → fixture list."""

    def _sync_matches(self, fixtures: list[dict], db: Session):
        """Create or update Match records from API response."""

    def _sync_events(self, fixture: dict, match: Match, db: Session):
        """Update Match.events from fixture events."""

    def _resolve_team(self, api_team_name: str, db: Session) -> int | None:
        """Match API team name to local Team by name/aliases."""

    def _determine_interval(self) -> int:
        """Return seconds until next poll based on current state."""
```

Uses `httpx.AsyncClient` for async HTTP requests (already in the project's dependencies).

### Session Lifecycle

Each poll cycle creates its own `SessionLocal()` and closes it in a `try/finally` block, matching the pattern used in `main.py` (`_process_post`, `_snapshot_loop`). Sessions are never shared across cycles.

### Retry Strategy

On transient HTTP errors (429, 500, 502, 503, timeout):
- Retry once after 5 seconds
- On persistent failure, log warning and wait for next polling interval
- Matches the resilience pattern of `JetstreamCollector`'s exponential backoff

## Changes to Existing Files

### `backend/models/match.py`

Add field:
```python
external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
```

**Migration:** Since this is a dev project using SQLite, delete `xingometro.db` to recreate with the new schema. The seed data and demo script will repopulate it. Document this in the commit message.

### `backend/config.py`

Add:
```python
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root

FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"
FOOTBALL_LEAGUE_ID = 71
FOOTBALL_SEASON = int(os.environ.get("FOOTBALL_SEASON", datetime.now().year))
```

Note: `FOOTBALL_SEASON` defaults to the current year, so it won't break at year boundaries.

### `backend/main.py`

In `lifespan()` startup:
```python
if FOOTBALL_API_KEY:
    football_collector = FootballAPICollector(FOOTBALL_API_KEY, FOOTBALL_LEAGUE_ID, FOOTBALL_SEASON)
    football_task = asyncio.create_task(football_collector.start())
    logger.info("Football API collector started")
else:
    football_collector = None
    football_task = None
    logger.info("No FOOTBALL_API_KEY — using seed data only")
```

In `lifespan()` shutdown:
```python
if football_collector:
    await football_collector.stop()
if football_task:
    football_task.cancel()
```

API-created matches use auto-generated IDs (omit `id` field). Seed match IDs are in a low range (1-10) and won't collide with autoincrement.

### `.env` (new, already in .gitignore)

```
FOOTBALL_API_KEY=your_key_here
```

### `requirements.txt` / dependencies

Add:
- `python-dotenv` — load .env file automatically

Note: `httpx` (already installed) provides `AsyncClient` for async HTTP — no new HTTP dependency needed.

## Graceful Fallback

If `FOOTBALL_API_KEY` is empty or API is unreachable:
- System continues working with seed JSON data
- Existing matches in DB are not affected
- Jetstream collector and dashboard function normally
- Logs a warning at startup

## Team Name Resolution

API-Football uses Portuguese team names (e.g., "Corinthians", "Flamengo") which should match our `Team.name` directly. For edge cases (e.g., "Atletico-MG" vs "Atlético Mineiro"), we check against `Team.aliases` as fallback.

Resolution order:
1. Exact match on `Team.name`
2. Exact match on `Team.short_name`
3. Substring match on `Team.aliases`
4. Log warning and skip if no match

## Not In Scope

- Historical season import (only current round + live)
- Coach updates from API (coaches stay manual in coaches.json)
- Team logo/crest URLs
- Player statistics
- Odds or predictions data
