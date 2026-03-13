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

# CORS
FRONTEND_URL = "http://localhost:5173"

# football-data.org v4
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://api.football-data.org/v4"
FOOTBALL_COMPETITION = "BSA"  # Brasileirão Série A
