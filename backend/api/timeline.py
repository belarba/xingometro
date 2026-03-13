from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.post import Post
from backend.models.match import Match

router = APIRouter()


@router.get("/timeline/{match_id}")
def get_timeline(match_id: int, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return {"error": "Match not found"}

    if not match.started_at:
        return {"points": [], "events": match.events or []}

    # Get posts grouped by minute intervals (5-min buckets)
    posts = (
        db.query(Post)
        .filter(Post.match_id == match_id)
        .order_by(Post.created_at)
        .all()
    )

    # Group into minute buckets
    buckets: dict[int, list[float]] = {}
    for post in posts:
        if match.started_at and post.created_at:
            delta = (post.created_at - match.started_at).total_seconds()
            minute = max(0, int(delta / 60))
            if minute <= 120:  # Cap at 120 minutes
                bucket = (minute // 5) * 5
                buckets.setdefault(bucket, []).append(post.rage_score)

    points = [
        {
            "minute": minute,
            "avg_rage_score": round(sum(scores) / len(scores), 1),
            "post_count": len(scores),
        }
        for minute, scores in sorted(buckets.items())
    ]

    return {
        "points": points,
        "events": match.events or [],
    }
