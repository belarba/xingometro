# Xingômetro dos Times do Brasil ⚽🔥

Dashboard de análise de sentimento em tempo real que monitora xingamentos de torcedores durante jogos do Brasileirão Série A, coletando posts do Bluesky, Twitter/X e Reddit.

## Como funciona

```
Bluesky (Jetstream) ──┐
Twitter/X (twscrape) ──┼──→ Filtro ──→ Análise de Rage ──→ Dashboard em tempo real
Reddit (API) ──────────┘         ↓
                          Dicionário de
                          palavrões (PT-BR)
```

1. **Coleta** — Posts são capturados em tempo real de múltiplas fontes
2. **Filtro** — Apenas posts sobre futebol/times são processados
3. **Análise** — Um scorer calcula o "rage score" (0-10) baseado em palavrões, CAPS LOCK, repetições e intensidade
4. **Detecção de alvo** — Identifica qual time/técnico está sendo xingado usando proximidade textual
5. **Broadcast** — Resultados são enviados via SSE para o dashboard

## Stack

### Backend
- **Python 3.10+** / FastAPI / Uvicorn
- **SQLAlchemy** + SQLite
- **SSE** (Server-Sent Events) para atualizações em tempo real
- **Collectors**: Bluesky Jetstream (WebSocket), Twitter/X (twscrape + ntscraper + xcancel), Reddit API
- **football-data.org** para dados de jogos/rodadas

### Frontend
- **React 18** + TypeScript + Vite
- **Tailwind CSS**
- **Recharts** para gráficos

## Pré-requisitos

- Python 3.10+ (recomendado 3.13)
- Node.js 18+
- Conta no [football-data.org](https://www.football-data.org/) (free tier)
- (Opcional) Conta Twitter/X para coleta via twscrape
- (Opcional) App Reddit para coleta via API

## Setup

### 1. Clone e configure o ambiente

```bash
git clone https://github.com/seu-usuario/xingometro-times.git
cd xingometro-times

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```env
# Obrigatório — football-data.org
FOOTBALL_API_KEY=sua_chave_aqui

# Opcional — Twitter/X (via cookies do browser)
TWITTER_COOKIES="auth_token=xxx; ct0=yyy"

# Opcional — Reddit
REDDIT_CLIENT_ID=seu_client_id
REDDIT_CLIENT_SECRET=seu_client_secret
```

**Para obter os cookies do Twitter:**
1. Faça login no X/Twitter no browser
2. Abra DevTools (F12) → Application → Cookies → x.com
3. Copie os valores de `auth_token` e `ct0`

### 3. Inicie o projeto

```bash
# Terminal 1 — Backend
source .venv/bin/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Acesse: **http://localhost:5173**

## Arquitetura

```
xingometro-times/
├── backend/
│   ├── api/                 # Endpoints REST + SSE
│   │   ├── rankings.py      # Ranking de xingamentos por time
│   │   ├── timeline.py      # Timeline de rage durante jogos
│   │   ├── stats.py         # Estatísticas gerais
│   │   ├── matches.py       # Dados de jogos/rodadas
│   │   └── live.py          # SSE broadcast
│   ├── analyzer/
│   │   ├── dictionary.py    # Dicionário de palavrões PT-BR
│   │   ├── scorer.py        # Cálculo do rage score (0-10)
│   │   └── target_detector.py  # Detecção de time/técnico alvo
│   ├── collector/
│   │   ├── jetstream.py     # Bluesky firehose (WebSocket)
│   │   ├── twitter.py       # Twitter/X (3 providers com fallback)
│   │   ├── reddit.py        # Reddit API (OAuth2)
│   │   ├── football_api.py  # football-data.org (dados de jogos)
│   │   └── filters.py       # Filtro de posts relevantes
│   ├── models/              # SQLAlchemy models
│   ├── data/                # Seed data (times, técnicos, palavrões)
│   ├── config.py            # Configuração centralizada
│   └── main.py              # Entrypoint + pipeline
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Navbar.tsx       # Header com status de conexão
│       │   ├── RageRanking.tsx  # Ranking de times por rage
│       │   ├── RageTimeline.tsx # Gráfico temporal de rage
│       │   ├── TopCoach.tsx     # Ranking de técnicos
│       │   ├── WordCloud.tsx    # Nuvem de palavras
│       │   ├── LiveFeed.tsx     # Feed de posts em tempo real
│       │   └── RoundFilter.tsx  # Filtro por rodada
│       ├── hooks/           # Custom hooks (SSE, polling)
│       ├── services/        # API client
│       └── types/           # TypeScript interfaces
└── .env                     # Credenciais (não commitado)
```

## Collectors

| Fonte | Tipo | Requisito | Dados |
|-------|------|-----------|-------|
| **Bluesky** | WebSocket (tempo real) | Nenhum | Posts públicos do firehose |
| **Twitter/X** | Polling (2-30min) | Cookies do browser | Busca por termos dos times |
| **Reddit** | Polling (30s) | App OAuth2 | Posts e comentários de 11 subs |
| **football-data.org** | Polling adaptativo | API key (free) | Jogos, placares, eventos |

### Twitter — Fallback Chain

O collector do Twitter usa 3 providers em cascata:

1. **twscrape** (primário) — Acesso direto à GraphQL API do Twitter via cookies
2. **ntscraper** (fallback) — Busca via instância Nitter/xcancel.com
3. **xcancel-scraper** (último recurso) — Scraping direto do HTML do xcancel.com

Se um provider falha, o próximo assume automaticamente.

## API Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/rankings` | Ranking de times por rage score |
| GET | `/api/rankings/coaches` | Ranking de técnicos |
| GET | `/api/timeline/{match_id}` | Timeline de rage de um jogo |
| GET | `/api/matches` | Lista de jogos (filtro por rodada) |
| GET | `/api/rounds` | Rodadas disponíveis |
| GET | `/api/words` | Palavras mais usadas |
| GET | `/api/live/feed` | SSE — posts em tempo real |
| GET | `/api/live/rankings` | SSE — rankings atualizados |
| GET | `/api/live/status` | Status de conexão |

## Rage Score

O score de raiva (0-10) é calculado com base em:

- **Base**: peso do palavrão mais forte encontrado
- **Multiplicadores**:
  - +20% se > 50% do texto em CAPS LOCK
  - +10% se tem caracteres repetidos (ex: "aaaargh")
  - +10% se tem 3+ exclamações
  - +30% se tem 4+ palavrões diferentes
- **Cap**: máximo 10.0

## Licença

MIT
