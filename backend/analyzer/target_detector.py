import json
import re
from dataclasses import dataclass

from unidecode import unidecode

from backend.config import DATA_DIR


@dataclass
class TargetResult:
    team_id: int | None = None
    coach_id: int | None = None


class TargetDetector:
    def __init__(self):
        self._teams: list[dict] = []
        self._coaches: list[dict] = []
        self._team_patterns: list[tuple[re.Pattern, int]] = []
        self._coach_patterns: list[tuple[re.Pattern, int, int]] = []
        self._load()

    def _load(self):
        with open(DATA_DIR / "teams.json", encoding="utf-8") as f:
            self._teams = json.load(f)
        with open(DATA_DIR / "coaches.json", encoding="utf-8") as f:
            self._coaches = json.load(f)

        for team in self._teams:
            names = [team["name"], team["short_name"]] + team.get("aliases", [])
            for name in names:
                pattern = re.compile(
                    r"\b" + re.escape(self._normalize(name)) + r"\b", re.IGNORECASE
                )
                self._team_patterns.append((pattern, team["id"]))

        for coach in self._coaches:
            names = [coach["name"]] + coach.get("aliases", [])
            for name in names:
                pattern = re.compile(
                    r"\b" + re.escape(self._normalize(name)) + r"\b", re.IGNORECASE
                )
                self._coach_patterns.append(
                    (pattern, coach["id"], coach["team_id"])
                )

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

        # Find coach mentions
        for pattern, coach_id, coach_team_id in self._coach_patterns:
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
