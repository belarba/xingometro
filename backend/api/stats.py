from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.match import Match
from backend.models.post import Post
from backend.models.team import Team

router = APIRouter()

# Cache for position history (expensive computation)
_position_cache: dict[int, dict] = {}
_POSITION_CACHE_TTL = 300  # 5 minutes


@router.get("/words")
def get_top_words(
    round_num: Optional[int] = Query(None, alias="round"),
    team_id: Optional[int] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
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


@router.get("/stats/correlation")
def get_correlation(
    round_num: Optional[int] = Query(None, alias="round"),
    db: Session = Depends(get_db),
):
    """Per-team-per-match correlation between goal diff and rage score."""
    # Single aggregated query for post stats grouped by match_id + team_id
    post_query = (
        db.query(
            Post.match_id,
            Post.team_id,
            func.count(Post.id).label("post_count"),
            func.avg(Post.rage_score).label("avg_rage"),
        )
        .filter(Post.team_id.isnot(None), Post.match_id.isnot(None))
        .group_by(Post.match_id, Post.team_id)
    )
    post_stats_map: dict[tuple[int, int], tuple[int, float]] = {}
    for row in post_query.all():
        post_stats_map[(row.match_id, row.team_id)] = (row.post_count, row.avg_rage or 0)

    # Get all finished matches, optionally filtered by round
    match_query = db.query(Match).filter(Match.status == "finished")
    if round_num is not None:
        match_query = match_query.filter(Match.round == round_num)
    matches = match_query.all()

    # Collect all team IDs we need
    team_ids = set()
    for match in matches:
        team_ids.add(match.home_team_id)
        team_ids.add(match.away_team_id)

    # Batch load teams
    teams = {t.id: t for t in db.query(Team).filter(Team.id.in_(team_ids)).all()}

    results = []
    for match in matches:
        for is_home in [True, False]:
            tid = match.home_team_id if is_home else match.away_team_id
            stats = post_stats_map.get((match.id, tid))
            if not stats or stats[0] == 0:
                continue

            team = teams.get(tid)
            if not team:
                continue

            goal_diff = (match.home_score - match.away_score) if is_home else (match.away_score - match.home_score)

            results.append({
                "match_id": match.id,
                "team_id": tid,
                "team_name": team.name,
                "short_name": team.short_name,
                "goal_diff": goal_diff,
                "avg_rage_score": round(stats[1], 1),
                "post_count": stats[0],
            })

    return results


@router.get("/stats/position-history/{team_id}")
def get_position_history(team_id: int, db: Session = Depends(get_db)):
    """Team's league position across rounds with rage data."""

    now = time.time()
    cached = _position_cache.get(team_id)
    if cached and (now - cached["timestamp"]) < _POSITION_CACHE_TTL:
        return cached["data"]

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get all finished matches ordered by round
    finished = (
        db.query(Match)
        .filter(Match.status == "finished")
        .order_by(Match.round)
        .all()
    )
    if not finished:
        return []

    max_round = max(m.round for m in finished)

    # Build cumulative standings round by round
    team_points: dict[int, dict] = {}  # team_id -> {points, gd, gf}
    results = []

    for round_num in range(1, max_round + 1):
        round_matches = [m for m in finished if m.round == round_num]

        for m in round_matches:
            for tid, is_home in [(m.home_team_id, True), (m.away_team_id, False)]:
                if tid not in team_points:
                    team_points[tid] = {"points": 0, "gd": 0, "gf": 0}
                gf = m.home_score if is_home else m.away_score
                ga = m.away_score if is_home else m.home_score
                if gf > ga:
                    team_points[tid]["points"] += 3
                elif gf == ga:
                    team_points[tid]["points"] += 1
                team_points[tid]["gd"] += gf - ga
                team_points[tid]["gf"] += gf

        # Sort to determine positions (points, then gd, then gf)
        sorted_teams = sorted(
            team_points.keys(),
            key=lambda t: (
                team_points[t]["points"],
                team_points[t]["gd"],
                team_points[t]["gf"],
            ),
            reverse=True,
        )

        position = sorted_teams.index(team_id) + 1 if team_id in sorted_teams else None
        if position is None:
            continue

        # Find this team's match in this round
        team_match = next(
            (m for m in round_matches if m.home_team_id == team_id or m.away_team_id == team_id),
            None,
        )

        score = ""
        result_code = "E"
        if team_match:
            is_home = team_match.home_team_id == team_id
            gf = team_match.home_score if is_home else team_match.away_score
            ga = team_match.away_score if is_home else team_match.home_score
            score = f"{gf}x{ga}"
            if gf > ga:
                result_code = "V"
            elif gf < ga:
                result_code = "D"

        # Get avg rage for this team in this round
        rage_stats = (
            db.query(func.avg(Post.rage_score))
            .join(Match, Post.match_id == Match.id)
            .filter(
                Match.round == round_num,
                Post.team_id == team_id,
                Post.team_id.isnot(None),
                Post.match_id.isnot(None),
            )
            .scalar()
        )

        results.append({
            "round": round_num,
            "position": position,
            "avg_rage_score": round(rage_stats or 0, 1),
            "result": result_code,
            "score": score,
        })

    _position_cache[team_id] = {"data": results, "timestamp": now}
    return results


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
