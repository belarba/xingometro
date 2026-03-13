from pathlib import Path

BASE_DIR = Path(__file__).parent
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
