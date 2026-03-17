import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import func, inspect as sa_inspect, text

from backend.config import (
    DATA_DIR, FRONTEND_URL, SNAPSHOT_INTERVAL, PROJECT_ROOT,
    FOOTBALL_API_KEY, FOOTBALL_API_BASE, FOOTBALL_COMPETITION,
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_SUBREDDITS, REDDIT_POLL_INTERVAL,
    TWITTER_COOKIES, TWITTER_USERNAME, TWITTER_PASSWORD, TWITTER_EMAIL, TWITTER_EMAIL_PASSWORD,
)
from backend.collector.football_api import FootballAPICollector
from backend.collector.reddit import RedditCollector
from backend.collector.twitter import TwitterCollector
from backend.models.database import init_db, SessionLocal, engine
from backend.models.team import Team
from backend.models.coach import Coach, CoachAssignment
from backend.models.match import Match
from backend.models.post import Post
from backend.models.rage_snapshot import RageSnapshot
from backend.collector.jetstream import JetstreamCollector
from backend.collector.filters import is_football_post
from backend.collector.match_window import match_window
from backend.analyzer.dictionary import swear_dictionary
from backend.analyzer.scorer import calculate_rage
from backend.analyzer.target_detector import target_detector
from backend.api import rankings, timeline, stats, matches, live
from backend.api.live import broadcast_post, broadcast_ranking_update, set_connected

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# All team aliases for filtering
_all_team_aliases: list[str] = []


def _run_migrations():
    """Add new columns to existing tables if missing."""
    inspector = sa_inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("coaches")]
    if "external_id" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE coaches ADD COLUMN external_id TEXT UNIQUE"))
            conn.commit()
        logger.info("Migration: added external_id column to coaches")


def _load_seed_data():
    """Load teams, coaches, and matches from JSON seed files."""
    db = SessionLocal()
    try:
        if db.query(Team).count() > 0:
            return

        logger.info("Loading seed data...")

        with open(DATA_DIR / "teams.json", encoding="utf-8") as f:
            teams_data = json.load(f)
        for t in teams_data:
            db.add(
                Team(
                    id=t["id"],
                    name=t["name"],
                    short_name=t["short_name"],
                    aliases=t.get("aliases", []),
                )
            )
            _all_team_aliases.extend(t.get("aliases", []))
            _all_team_aliases.append(t["name"])
            _all_team_aliases.append(t["short_name"])

        with open(DATA_DIR / "coaches.json", encoding="utf-8") as f:
            coaches_data = json.load(f)
        for c in coaches_data:
            db.add(
                Coach(
                    id=c["id"],
                    name=c["name"],
                    aliases=c.get("aliases", []),
                    team_id=c["team_id"],
                )
            )

        with open(DATA_DIR / "matches.json", encoding="utf-8") as f:
            matches_data = json.load(f)
        for m in matches_data:
            started = None
            finished = None
            if m.get("started_at"):
                started = datetime.fromisoformat(m["started_at"])
            if m.get("finished_at"):
                finished = datetime.fromisoformat(m["finished_at"])
            db.add(
                Match(
                    id=m["id"],
                    round=m["round"],
                    home_team_id=m["home_team_id"],
                    away_team_id=m["away_team_id"],
                    home_score=m.get("home_score", 0),
                    away_score=m.get("away_score", 0),
                    status=m.get("status", "scheduled"),
                    events=m.get("events", []),
                    started_at=started,
                    finished_at=finished,
                )
            )

        db.commit()
        logger.info("Seed data loaded successfully")
    finally:
        db.close()


def _process_post(raw_post: dict):
    """Pipeline: match window → filter → analyze → persist → broadcast."""
    # Only process posts when matches are in the active window
    # (1h before kickoff until 2h after final whistle)
    if not match_window.is_active():
        return

    text = raw_post["text"]

    if not is_football_post(text, _all_team_aliases):
        return

    # Analyze
    swear_matches = swear_dictionary.find_matches(text)
    rage_score = calculate_rage(text, swear_matches)

    if rage_score == 0:
        return

    # Find swear word positions for disambiguation
    from unidecode import unidecode

    normalized = unidecode(text).lower()
    swear_positions = []
    for m in swear_matches:
        norm_word = unidecode(m.word).lower()
        idx = normalized.find(norm_word)
        if idx >= 0:
            swear_positions.append(idx)

    # Detect target
    target = target_detector.detect(text, swear_positions)

    # Only accept posts targeting teams with active matches
    active_teams = match_window.get_active_team_ids()
    if target.team_id and target.team_id not in active_teams:
        return

    # Find active match for this team
    match_id = None
    if target.team_id:
        db = SessionLocal()
        try:
            match = (
                db.query(Match)
                .filter(
                    Match.status == "live",
                    (
                        (Match.home_team_id == target.team_id)
                        | (Match.away_team_id == target.team_id)
                    ),
                )
                .first()
            )
            if match:
                match_id = match.id
        finally:
            db.close()

    # Persist
    db = SessionLocal()
    try:
        post = Post(
            source=raw_post["source"],
            external_id=raw_post["external_id"],
            author_handle=raw_post["author_handle"],
            text=text,
            team_id=target.team_id,
            coach_id=target.coach_id,
            match_id=match_id,
            rage_score=rage_score,
            swear_words=[m.word for m in swear_matches],
            created_at=raw_post["created_at"],
            analyzed_at=datetime.now(timezone.utc),
        )
        db.add(post)
        db.commit()

        # Broadcast to SSE
        team_name = (
            target_detector.get_team_name(target.team_id)
            if target.team_id
            else None
        )
        broadcast_post(
            {
                "id": post.id,
                "author_handle": post.author_handle,
                "text": post.text,
                "team_id": post.team_id,
                "team_name": team_name,
                "coach_id": post.coach_id,
                "rage_score": post.rage_score,
                "swear_words": post.swear_words,
                "created_at": post.created_at.isoformat(),
            }
        )
    except Exception as e:
        db.rollback()
        if "UNIQUE constraint" not in str(e):
            logger.error(f"Error persisting post: {e}")
    finally:
        db.close()


async def _snapshot_loop():
    """Periodically compute rage_snapshots for live matches."""
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        try:
            db = SessionLocal()
            try:
                live_matches = (
                    db.query(Match).filter(Match.status == "live").all()
                )
                for match in live_matches:
                    for team_id in [match.home_team_id, match.away_team_id]:
                        result = (
                            db.query(
                                func.count(Post.id),
                                func.avg(Post.rage_score),
                                func.max(Post.rage_score),
                            )
                            .filter(
                                Post.match_id == match.id,
                                Post.team_id == team_id,
                            )
                            .first()
                        )
                        if result and result[0] > 0:
                            # Top words
                            posts = (
                                db.query(Post.swear_words)
                                .filter(
                                    Post.match_id == match.id,
                                    Post.team_id == team_id,
                                )
                                .all()
                            )
                            word_counts: dict[str, int] = {}
                            for (words,) in posts:
                                if isinstance(words, list):
                                    for w in words:
                                        word_counts[w] = (
                                            word_counts.get(w, 0) + 1
                                        )

                            snapshot = RageSnapshot(
                                team_id=team_id,
                                match_id=match.id,
                                round=match.round,
                                period="match",
                                post_count=result[0],
                                avg_rage_score=round(result[1], 2),
                                max_rage_score=round(result[2], 2),
                                top_swear_words=dict(
                                    sorted(
                                        word_counts.items(),
                                        key=lambda x: x[1],
                                        reverse=True,
                                    )[:10]
                                ),
                                snapshot_at=datetime.now(timezone.utc),
                            )
                            db.add(snapshot)

                db.commit()

                # Broadcast updated rankings
                ranking_data = (
                    db.query(
                        Post.team_id,
                        Team.name.label("team_name"),
                        Team.short_name,
                        func.avg(Post.rage_score).label("avg_rage_score"),
                        func.count(Post.id).label("post_count"),
                    )
                    .join(Team, Post.team_id == Team.id)
                    .filter(Post.team_id.isnot(None))
                    .group_by(Post.team_id)
                    .order_by(func.avg(Post.rage_score).desc())
                    .limit(20)
                    .all()
                )
                broadcast_ranking_update(
                    [
                        {
                            "team_id": r.team_id,
                            "team_name": r.team_name,
                            "short_name": r.short_name,
                            "avg_rage_score": round(r.avg_rage_score, 1),
                            "post_count": r.post_count,
                        }
                        for r in ranking_data
                    ]
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Snapshot error: {e}")


collector = JetstreamCollector(on_post=_process_post)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _run_migrations()
    _load_seed_data()

    # Reload target detector from DB if we have coach assignments from a previous run
    db = SessionLocal()
    try:
        if db.query(CoachAssignment).first() is not None:
            target_detector.reload()
            logger.info("Reloaded target detector from DB coach assignments")
    finally:
        db.close()

    collector_task = asyncio.create_task(collector.start())
    set_connected(True)
    snapshot_task = asyncio.create_task(_snapshot_loop())

    # Football API collector (optional, needs API key)
    football_collector = None
    football_task = None
    if FOOTBALL_API_KEY:
        football_collector = FootballAPICollector(
            api_key=FOOTBALL_API_KEY,
            competition=FOOTBALL_COMPETITION,
            base_url=FOOTBALL_API_BASE,
        )
        football_task = asyncio.create_task(football_collector.start())
        logger.info("Football API collector started (competition=%s)", FOOTBALL_COMPETITION)
    else:
        logger.info("No FOOTBALL_API_KEY set — using seed data only")

    # Reddit collector (optional, needs OAuth credentials)
    reddit_collector = None
    reddit_task = None
    if REDDIT_CLIENT_ID:
        reddit_collector = RedditCollector(
            on_post=_process_post,
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            subreddits=REDDIT_SUBREDDITS,
            poll_interval=REDDIT_POLL_INTERVAL,
        )
        reddit_task = asyncio.create_task(reddit_collector.start())
        logger.info("Reddit collector started (%d subreddits)", len(REDDIT_SUBREDDITS))
    else:
        logger.info("No REDDIT_CLIENT_ID set — Reddit collector disabled")

    # Twitter collector (optional, needs cookies or credentials)
    twitter_collector = None
    twitter_task = None
    if TWITTER_COOKIES or TWITTER_USERNAME:
        twitter_collector = TwitterCollector(
            on_post=_process_post,
            cookies=TWITTER_COOKIES,
            username=TWITTER_USERNAME,
            password=TWITTER_PASSWORD,
            email=TWITTER_EMAIL,
            email_password=TWITTER_EMAIL_PASSWORD,
        )
        twitter_task = asyncio.create_task(twitter_collector.start())
        logger.info("Twitter collector started (twscrape + ntscraper + xcancel)")
    else:
        logger.info("No TWITTER_COOKIES/TWITTER_USERNAME set — Twitter collector disabled")

    logger.info("Xingômetro started! Collecting from Bluesky Jetstream...")
    yield

    set_connected(False)
    await collector.stop()
    snapshot_task.cancel()
    collector_task.cancel()

    if football_collector:
        await football_collector.stop()
    if football_task:
        football_task.cancel()

    if reddit_collector:
        await reddit_collector.stop()
    if reddit_task:
        reddit_task.cancel()

    if twitter_collector:
        await twitter_collector.stop()
    if twitter_task:
        twitter_task.cancel()


app = FastAPI(title="Xingômetro API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rankings.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(live.router, prefix="/api")

# --- Serve frontend static files in production ---
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        """Serve index.html for any non-API route (SPA client-side routing)."""
        file_path = FRONTEND_DIST / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
