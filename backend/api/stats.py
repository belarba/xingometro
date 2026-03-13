from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.post import Post
from backend.models.team import Team

router = APIRouter()


@router.get("/stats/{team_id}")
def get_team_stats(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return {"error": "Team not found"}

    stats = (
        db.query(
            func.count(Post.id).label("total_posts"),
            func.avg(Post.rage_score).label("avg_rage"),
            func.max(Post.rage_score).label("max_rage"),
        )
        .filter(Post.team_id == team_id)
        .first()
    )

    # Top swear words
    posts = (
        db.query(Post.swear_words)
        .filter(Post.team_id == team_id, Post.swear_words.isnot(None))
        .limit(1000)
        .all()
    )
    word_counts: dict[str, int] = {}
    for (words,) in posts:
        if isinstance(words, list):
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1
    top_words = dict(
        sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    )

    return {
        "team_id": team_id,
        "team_name": team.name,
        "total_posts": stats.total_posts or 0,
        "avg_rage_score": round(stats.avg_rage or 0, 1),
        "max_rage_score": round(stats.max_rage or 0, 1),
        "top_swear_words": top_words,
    }


@router.get("/words")
def get_top_words(
    round_num: Optional[int] = Query(None, alias="round"),
    team_id: Optional[int] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from backend.models.match import Match

    query = db.query(Post.swear_words).filter(Post.swear_words.isnot(None))

    if team_id is not None:
        query = query.filter(Post.team_id == team_id)
    if round_num is not None:
        query = query.join(Match, Post.match_id == Match.id).filter(
            Match.round == round_num
        )

    posts = query.limit(5000).all()

    word_counts: dict[str, int] = {}
    for (words,) in posts:
        if isinstance(words, list):
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1

    # Get level from dictionary
    from backend.analyzer.dictionary import swear_dictionary

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[
        :limit
    ]
    result = []
    for word, count in sorted_words:
        matches = swear_dictionary.find_matches(word)
        level = matches[0].level if matches else 1
        result.append({"word": word, "count": count, "level": level})

    return result
