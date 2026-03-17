"""API endpoint for Brasileirão standings from Football-Data.org."""
from __future__ import annotations

import logging
import time

import httpx
from fastapi import APIRouter, HTTPException

from backend.config import FOOTBALL_API_KEY, FOOTBALL_API_BASE, FOOTBALL_COMPETITION
from backend.models.database import SessionLocal
from backend.utils.team_resolver import team_resolver

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple TTL cache
_cache: dict = {"data": None, "timestamp": 0.0}
_CACHE_TTL = 30 * 60  # 30 minutes


async def _fetch_standings_from_api() -> list[dict]:
    """Fetch standings from Football-Data.org and resolve to local teams."""
    if not FOOTBALL_API_KEY:
        raise HTTPException(status_code=503, detail="Football API key not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{FOOTBALL_API_BASE}/competitions/{FOOTBALL_COMPETITION}/standings",
            headers={"X-Auth-Token": FOOTBALL_API_KEY},
        )
        if resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Football API rate limited")
        if resp.status_code >= 400:
            raise HTTPException(status_code=503, detail="Football API unavailable")
        data = resp.json()

    # Ensure resolver is loaded
    db = SessionLocal()
    try:
        team_resolver.load(db)
    finally:
        db.close()

    # Find TOTAL standings table
    standings = []
    for table in data.get("standings", []):
        if table.get("type") == "TOTAL":
            for entry in table.get("table", []):
                api_team_name = entry.get("team", {}).get("name", "")
                team_id = team_resolver.resolve(api_team_name)
                short_name = team_resolver.get_short_name(team_id) if team_id else None

                standings.append({
                    "position": entry.get("position"),
                    "team_id": team_id,
                    "team_name": api_team_name,
                    "short_name": short_name or "",
                    "played_games": entry.get("playedGames", 0),
                    "won": entry.get("won", 0),
                    "draw": entry.get("draw", 0),
                    "lost": entry.get("lost", 0),
                    "goals_for": entry.get("goalsFor", 0),
                    "goals_against": entry.get("goalsAgainst", 0),
                    "goal_difference": entry.get("goalDifference", 0),
                    "points": entry.get("points", 0),
                })
            break

    return standings


@router.get("/standings")
async def get_standings():
    now = time.time()
    if _cache["data"] is not None and (now - _cache["timestamp"]) < _CACHE_TTL:
        return _cache["data"]

    standings = await _fetch_standings_from_api()
    _cache["data"] = standings
    _cache["timestamp"] = now
    return standings
