from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.post import Post
from backend.models.team import Team
from backend.models.coach import Coach
from backend.models.match import Match

router = APIRouter()


@router.get("/rankings")
def get_rankings(
    round: int | None = Query(None),
    limit: int = Query(20, ge=1, le=20),
    db: Session = Depends(get_db),
):
    query = db.query(
        Post.team_id,
        Team.name.label("team_name"),
        Team.short_name,
        func.avg(Post.rage_score).label("avg_rage_score"),
        func.count(Post.id).label("post_count"),
    ).join(Team, Post.team_id == Team.id)

    if round is not None:
        query = query.join(Match, Post.match_id == Match.id).filter(
            Match.round == round
        )

    query = query.filter(Post.team_id.isnot(None))
    results = (
        query.group_by(Post.team_id)
        .order_by(func.avg(Post.rage_score).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "team_id": r.team_id,
            "team_name": r.team_name,
            "short_name": r.short_name,
            "avg_rage_score": round(r.avg_rage_score, 1) if r.avg_rage_score else 0,
            "post_count": r.post_count,
        }
        for r in results
    ]


@router.get("/rankings/coaches")
def get_coach_rankings(
    round: int | None = Query(None),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    query = db.query(
        Post.coach_id,
        Coach.name.label("coach_name"),
        Team.name.label("team_name"),
        func.avg(Post.rage_score).label("avg_rage_score"),
        func.count(Post.id).label("post_count"),
    ).join(Coach, Post.coach_id == Coach.id).join(Team, Coach.team_id == Team.id)

    if round is not None:
        query = query.join(Match, Post.match_id == Match.id).filter(
            Match.round == round
        )

    query = query.filter(Post.coach_id.isnot(None))
    results = (
        query.group_by(Post.coach_id)
        .order_by(func.avg(Post.rage_score).desc())
        .limit(limit)
        .all()
    )

    # Get top words for each coach
    rankings = []
    for r in results:
        # Aggregate swear_words from posts for this coach
        posts = (
            db.query(Post.swear_words)
            .filter(Post.coach_id == r.coach_id, Post.swear_words.isnot(None))
            .limit(500)
            .all()
        )
        word_counts: dict[str, int] = {}
        for (words,) in posts:
            if isinstance(words, list):
                for w in words:
                    word_counts[w] = word_counts.get(w, 0) + 1
        top_words = dict(
            sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        )

        rankings.append(
            {
                "coach_id": r.coach_id,
                "coach_name": r.coach_name,
                "team_name": r.team_name,
                "avg_rage_score": round(r.avg_rage_score, 1) if r.avg_rage_score else 0,
                "post_count": r.post_count,
                "top_words": top_words,
            }
        )

    return rankings
