from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.match import Match
from backend.models.team import Team

router = APIRouter()


@router.get("/matches")
def get_matches(
    round: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Match)

    if round is not None:
        query = query.filter(Match.round == round)
    if status is not None:
        query = query.filter(Match.status == status)

    matches = query.order_by(Match.started_at).all()

    # Fetch team names
    team_ids = set()
    for m in matches:
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)

    teams = {t.id: t for t in db.query(Team).filter(Team.id.in_(team_ids)).all()}

    return [
        {
            "id": m.id,
            "round": m.round,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_team_name": teams.get(m.home_team_id, None)
            and teams[m.home_team_id].name,
            "away_team_name": teams.get(m.away_team_id, None)
            and teams[m.away_team_id].name,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "status": m.status,
            "events": m.events or [],
            "started_at": m.started_at.isoformat() if m.started_at else None,
            "finished_at": m.finished_at.isoformat() if m.finished_at else None,
        }
        for m in matches
    ]


@router.get("/rounds")
def get_rounds(db: Session = Depends(get_db)):
    rounds = (
        db.query(distinct(Match.round))
        .order_by(Match.round)
        .all()
    )
    return [r[0] for r in rounds]


@router.post("/matches/{match_id}/events")
def add_match_event(match_id: int, event: dict, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return {"error": "Match not found"}

    events = list(match.events or [])
    events.append(event)
    match.events = events
    db.commit()

    return {"ok": True, "events": match.events}
