"""Manages the active match window for filtering posts.

Only processes posts when there are matches within the window:
- From 1 hour BEFORE the match starts
- Until 2 hours AFTER the match finishes (or 4h after start if no finish time)

Maintains a cached set of active team IDs, refreshed every 60 seconds.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta

from backend.models.database import SessionLocal
from backend.models.match import Match

logger = logging.getLogger(__name__)

# Window parameters
PRE_MATCH = timedelta(hours=1)
POST_MATCH = timedelta(hours=2)
FALLBACK_DURATION = timedelta(hours=4)  # if finished_at is unknown

# Cache refresh interval
_CACHE_TTL = 60  # seconds


class MatchWindow:
    """Tracks which teams have matches in the active window."""

    def __init__(self):
        self._active_team_ids: set[int] = set()
        self._last_refresh: float = 0
        self._any_match_active: bool = False

    def is_active(self) -> bool:
        """Return True if any match is currently in the active window."""
        self._maybe_refresh()
        return self._any_match_active

    def get_active_team_ids(self) -> set[int]:
        """Return team IDs that have matches in the active window."""
        self._maybe_refresh()
        return self._active_team_ids

    def _maybe_refresh(self):
        """Refresh cache if TTL expired."""
        now = time.monotonic()
        if now - self._last_refresh < _CACHE_TTL:
            return
        self._last_refresh = now
        self._refresh()

    def _refresh(self):
        """Query DB for matches in the active window."""
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            matches = (
                db.query(Match)
                .filter(Match.started_at.isnot(None))
                .all()
            )

            active_ids: set[int] = set()
            for m in matches:
                window_start = m.started_at - PRE_MATCH
                if m.finished_at:
                    window_end = m.finished_at + POST_MATCH
                else:
                    # For live or scheduled matches without finish time
                    window_end = m.started_at + FALLBACK_DURATION

                if window_start <= now <= window_end:
                    active_ids.add(m.home_team_id)
                    active_ids.add(m.away_team_id)

            prev_active = self._any_match_active
            self._active_team_ids = active_ids
            self._any_match_active = len(active_ids) > 0

            if self._any_match_active and not prev_active:
                logger.info(
                    "Match window OPENED — %d teams active", len(active_ids)
                )
            elif not self._any_match_active and prev_active:
                logger.info("Match window CLOSED — no active matches")

        except Exception as e:
            logger.error("Error refreshing match window: %s", e)
        finally:
            db.close()


# Singleton
match_window = MatchWindow()
