from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "xingometro.db"

JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe"

# Termos para filtrar posts relevantes do firehose
FOOTBALL_TERMS = [
    "brasileirão", "brasileirao", "serie a", "série a",
    "futebol", "gol", "jogo", "rodada", "campeonato",
    "arbitro", "árbitro", "juiz", "var",
    "escalação", "escalacao", "titular", "reserva",
]

# Intervalo em segundos para atualizar rage_snapshots
SNAPSHOT_INTERVAL = 30

# Máximo de posts no feed SSE (buffer)
SSE_BUFFER_SIZE = 50

# CORS — in production, set FRONTEND_URL to your Railway domain
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Port (Railway sets PORT env var)
PORT = int(os.environ.get("PORT", "8000"))

# football-data.org v4
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://api.football-data.org/v4"
FOOTBALL_COMPETITION = "BSA"  # Brasileirão Série A

# Reddit (optional collector)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_SUBREDDITS = [
    "futebol", "CRFla", "palmeiras", "Corinthians", "SaoPauloFC",
    "Vasco", "botafogo", "internacional", "gremio", "Cruzeiro", "atleticomg",
]
REDDIT_POLL_INTERVAL = 30

# Twitter/X (optional collector — twscrape + ntscraper + xcancel fallback)
TWITTER_COOKIES = os.environ.get("TWITTER_COOKIES", "")
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD", "")
TWITTER_EMAIL = os.environ.get("TWITTER_EMAIL", "")
TWITTER_EMAIL_PASSWORD = os.environ.get("TWITTER_EMAIL_PASSWORD", "")
