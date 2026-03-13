from __future__ import annotations

from unidecode import unidecode

from backend.config import FOOTBALL_TERMS


def _normalize(text: str) -> str:
    return unidecode(text).lower()


# Pre-normalize terms for faster matching
_NORMALIZED_TERMS = [_normalize(t) for t in FOOTBALL_TERMS]


def is_football_post(text: str, team_aliases: list[str] | None = None) -> bool:
    """Check if a post is related to Brazilian football."""
    normalized = _normalize(text)

    # Check football terms
    for term in _NORMALIZED_TERMS:
        if term in normalized:
            return True

    # Check team aliases if provided
    if team_aliases:
        for alias in team_aliases:
            if _normalize(alias) in normalized:
                return True

    return False
