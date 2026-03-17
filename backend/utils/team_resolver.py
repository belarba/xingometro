"""Shared utility: resolve external team names to local team IDs."""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from backend.models.team import Team


class TeamResolver:
    """Resolves API team names to local team IDs using name/alias matching."""

    def __init__(self):
        self._cache: dict[str, int] = {}
        self._short_names: dict[int, str] = {}

    def load(self, db: Session):
        """Build name -> id and id -> short_name caches from DB."""
        self._cache.clear()
        self._short_names.clear()
        teams = db.query(Team).all()
        for team in teams:
            self._cache[team.name.lower()] = team.id
            self._cache[team.short_name.lower()] = team.id
            self._short_names[team.id] = team.short_name
            if team.aliases:
                for alias in team.aliases:
                    self._cache[alias.lower()] = team.id

    def resolve(self, api_name: str) -> Optional[int]:
        """Resolve API team name to local team ID."""
        if not api_name:
            return None
        name_lower = api_name.lower()
        # Exact match
        if name_lower in self._cache:
            return self._cache[name_lower]
        # Substring match
        for cached_name, team_id in self._cache.items():
            if cached_name in name_lower or name_lower in cached_name:
                return team_id
        return None

    def get_short_name(self, team_id: int) -> Optional[str]:
        """Get short_name for a team_id."""
        return self._short_names.get(team_id)


# Singleton instance
team_resolver = TeamResolver()
