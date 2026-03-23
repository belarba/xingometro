from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from unidecode import unidecode

from backend.config import DATA_DIR

logger = logging.getLogger(__name__)


@dataclass
class TargetResult:
    team_id: int | None = None
    coach_id: int | None = None


class TargetDetector:
    def __init__(self):
        self._teams: list[dict] = []
        self._team_patterns: list[tuple[re.Pattern, int]] = []
        self._coach_patterns: list[tuple[re.Pattern, int, int]] = []
        self._load_from_json()

    def _load_from_json(self):
        """Load teams and coaches from static JSON files (initial/fallback)."""
        with open(DATA_DIR / "teams.json", encoding="utf-8") as f:
            self._teams = json.load(f)
        with open(DATA_DIR / "coaches.json", encoding="utf-8") as f:
            coaches = json.load(f)

        self._team_patterns = self._build_team_patterns(self._teams)
        self._coach_patterns = self._build_coach_patterns(coaches)

    def reload(self):
        """Reload coach patterns from the database.

        Uses atomic reference swap — builds a new list then replaces the
        reference, so detect() never sees a partially-built list.
        """
        from backend.models.database import SessionLocal
        from backend.models.coach import Coach

        db = SessionLocal()
        try:
            coaches = db.query(Coach).all()
            if not coaches:
                return

            coach_dicts = [
                {
                    "id": c.id,
                    "name": c.name,
                    "aliases": c.aliases or [],
                    "team_id": c.team_id,
                }
                for c in coaches
            ]
            new_patterns = self._build_coach_patterns(coach_dicts)
            # Atomic swap
            self._coach_patterns = new_patterns
            logger.info("TargetDetector reloaded %d coaches from DB", len(coaches))
        finally:
            db.close()

    # Minimum alias length for pattern matching to avoid matching
    # common Portuguese words (e.g. "SAO" → "são", "FOR" → "for")
    _MIN_PATTERN_LENGTH = 3

    @staticmethod
    def _build_team_patterns(teams: list[dict]) -> list[tuple[re.Pattern, int]]:
        patterns = []
        for team in teams:
            # Skip short_name — 3-char codes like SAO, INT, FOR match
            # common Portuguese words and cause false positives
            names = [team["name"]] + team.get("aliases", [])
            for name in names:
                normalized = TargetDetector._normalize(name)
                if len(normalized) < TargetDetector._MIN_PATTERN_LENGTH:
                    continue
                pattern = re.compile(
                    r"\b" + re.escape(normalized) + r"\b",
                    re.IGNORECASE,
                )
                patterns.append((pattern, team["id"]))
        return patterns

    @staticmethod
    def _build_coach_patterns(
        coaches: list[dict],
    ) -> list[tuple[re.Pattern, int, int]]:
        patterns = []
        for coach in coaches:
            names = [coach["name"]] + coach.get("aliases", [])
            for name in names:
                pattern = re.compile(
                    r"\b" + re.escape(TargetDetector._normalize(name)) + r"\b",
                    re.IGNORECASE,
                )
                patterns.append((pattern, coach["id"], coach["team_id"]))
        return patterns

    @staticmethod
    def _normalize(text: str) -> str:
        return unidecode(text).lower().strip()

    def detect(
        self, text: str, swear_positions: list[int] | None = None
    ) -> TargetResult:
        normalized = self._normalize(text)
        result = TargetResult()

        # Find all team mentions with their positions
        team_mentions: list[tuple[int, int, int]] = []  # (start, end, team_id)
        for pattern, team_id in self._team_patterns:
            for match in pattern.finditer(normalized):
                team_mentions.append((match.start(), match.end(), team_id))

        # Find coach mentions (read reference once for consistency)
        coach_patterns = self._coach_patterns
        for pattern, coach_id, coach_team_id in coach_patterns:
            if pattern.search(normalized):
                result.coach_id = coach_id
                if result.team_id is None:
                    result.team_id = coach_team_id
                break

        if not team_mentions:
            return result

        # Deduplicate by team_id (keep first occurrence)
        seen_teams: dict[int, tuple[int, int]] = {}
        for start, end, team_id in team_mentions:
            if team_id not in seen_teams:
                seen_teams[team_id] = (start, end)

        unique_teams = list(seen_teams.keys())

        if len(unique_teams) == 1:
            result.team_id = unique_teams[0]
            return result

        # Disambiguation: find which team is closest to swear words
        if swear_positions:
            best_team = None
            best_distance = float("inf")
            for team_id, (start, _end) in seen_teams.items():
                min_dist = min(abs(start - sp) for sp in swear_positions)
                if min_dist < best_distance:
                    best_distance = min_dist
                    best_team = team_id
            result.team_id = best_team
        else:
            # Default: first mentioned team
            result.team_id = unique_teams[0]

        return result

    def get_team_name(self, team_id: int) -> str:
        for team in self._teams:
            if team["id"] == team_id:
                return team["name"]
        return "Desconhecido"

    def get_live_team_ids(self, live_match_team_ids: set[int]) -> set[int]:
        return live_match_team_ids


# Singleton
target_detector = TargetDetector()
