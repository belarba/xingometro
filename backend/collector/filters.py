from __future__ import annotations

import re

from unidecode import unidecode

from backend.config import FOOTBALL_TERMS

# Minimum alias length to avoid matching common Portuguese words
# (e.g. "SAO" → "são", "FOR" → "for")
_MIN_ALIAS_LENGTH = 3


def _normalize(text: str) -> str:
    return unidecode(text).lower()


# Pre-normalize terms for faster matching
_NORMALIZED_TERMS = [_normalize(t) for t in FOOTBALL_TERMS]

# Pre-compiled word-boundary patterns for team aliases (built lazily)
_alias_patterns: list[re.Pattern] | None = None


def _build_alias_patterns(aliases: list[str]) -> list[re.Pattern]:
    """Build word-boundary regex patterns from aliases, skipping short ones."""
    patterns = []
    for alias in aliases:
        normalized = _normalize(alias)
        if len(normalized) < _MIN_ALIAS_LENGTH:
            continue
        pattern = re.compile(r"\b" + re.escape(normalized) + r"\b")
        patterns.append(pattern)
    return patterns


def is_football_post(text: str, team_aliases: list[str] | None = None) -> bool:
    """Check if a post is related to Brazilian football.

    Uses word-boundary matching for team aliases to avoid false positives
    from common Portuguese words (e.g. "são" matching São Paulo).
    """
    global _alias_patterns
    normalized = _normalize(text)

    # Check football terms (substring is fine — these are specific enough)
    for term in _NORMALIZED_TERMS:
        if term in normalized:
            return True

    # Check team aliases with word-boundary matching
    if team_aliases:
        if _alias_patterns is None:
            _alias_patterns = _build_alias_patterns(team_aliases)
        for pattern in _alias_patterns:
            if pattern.search(normalized):
                return True

    return False
