# Xingômetro — Design Spec

Análise de sentimento em tempo real de posts do Bluesky durante jogos do Brasileirão. Mede a agressividade textual das torcidas, identifica o time mais xingado, o técnico que gera mais revolta e as palavras mais usadas por rodada.

## Arquitetura

**Abordagem: Monolito Inteligente** — um único processo FastAPI que coleta, analisa e serve dados.

### Stack

- **Backend**: Python 3.12+ / FastAPI / SQLite (via SQLAlchemy)
- **Frontend**: React 18 / Vite / Recharts (gráficos) / TailwindCSS
- **Coleta**: Bluesky Jetstream (WebSocket)
- **Comunicação live**: Server-Sent Events (SSE) do backend para o frontend
- **Deploy**: um único processo (uvicorn)

### Fluxo de Dados

```
Bluesky Jetstream ──WebSocket──▶ Collector (background task)
                                      │
                                      ▼ filtra por termos do futebol BR
                                 Analyzer
                                      │ identifica time/técnico
                                      │ calcula rage_score via dicionário
                                      ▼
                                   SQLite
                                      │ persiste posts + agregações
                                      ▼
                                   FastAPI
                                      │ REST (histórico) + SSE (live)
                                      ▼
                                React Dashboard
```

### Módulos do Backend

```
backend/
├── main.py                 # FastAPI app, startup/shutdown, CORS
├── collector/
│   ├── jetstream.py        # Conexão WebSocket ao Bluesky Jetstream
│   └── filters.py          # Filtragem por termos/hashtags do futebol BR
├── analyzer/
│   ├── dictionary.py       # Carrega e busca no dicionário de xingamentos
│   ├── scorer.py           # Calcula rage_score com multiplicadores
│   └── target_detector.py  # Identifica time/técnico alvo
├── models/
│   ├── database.py         # Engine SQLite, session factory
│   ├── team.py             # Model Team
│   ├── coach.py            # Model Coach
│   ├── match.py            # Model Match
│   ├── post.py             # Model Post
│   └── rage_snapshot.py    # Model RageSnapshot (agregação)
├── api/
│   ├── rankings.py         # GET /rankings (por rodada, geral)
│   ├── timeline.py         # GET /timeline/{match_id}
│   ├── stats.py            # GET /stats/{team_id}, /stats/coaches
│   ├── live.py             # GET /live/feed (SSE stream)
│   └── matches.py          # GET /matches, GET /rounds
├── data/
│   ├── swear_dictionary.json   # Dicionário de xingamentos com pesos
│   ├── teams.json              # Times do Brasileirão com aliases
│   ├── coaches.json            # Técnicos com aliases
│   └── matches.json            # Jogos da rodada (seed data com horários)
└── config.py               # Settings (Jetstream URL, DB path, etc.)
```

### Estrutura do Frontend

```
frontend/
├── src/
│   ├── App.tsx
│   ├── components/
│   │   ├── RageRanking.tsx       # Barras horizontais de ranking
│   │   ├── RageTimeline.tsx      # Gráfico temporal com anotações
│   │   ├── TopCoach.tsx          # Card do técnico mais xingado
│   │   ├── WordCloud.tsx         # Nuvem de palavras
│   │   ├── LiveFeed.tsx          # Feed de posts em tempo real
│   │   ├── RoundFilter.tsx       # Seletor de rodada
│   │   └── Navbar.tsx            # Header com status live
│   ├── hooks/
│   │   ├── useSSE.ts             # Hook para consumir SSE
│   │   └── useRankings.ts        # Hook para dados de ranking
│   ├── services/
│   │   └── api.ts                # Client HTTP para o backend
│   └── types/
│       └── index.ts              # TypeScript types
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Modelo de Dados

### teams

| Coluna     | Tipo    | Descrição                                      |
|------------|---------|-------------------------------------------------|
| id         | INTEGER | PK autoincrement                                |
| name       | TEXT    | Nome oficial ("Flamengo")                       |
| short_name | TEXT    | Sigla ("FLA")                                   |
| aliases    | JSON    | Lista de apelidos ["mengão", "mengo", "urubu"]  |

### coaches

| Coluna  | Tipo    | Descrição                          |
|---------|---------|------------------------------------|
| id      | INTEGER | PK autoincrement                   |
| name    | TEXT    | Nome ("Tite")                      |
| aliases | JSON    | Apelidos ["adenor"]                |
| team_id | INTEGER | FK → teams (técnico pertence ao time) |

### matches

| Coluna       | Tipo     | Descrição                          |
|--------------|----------|------------------------------------|
| id           | INTEGER  | PK autoincrement                   |
| round        | INTEGER  | Número da rodada                   |
| home_team_id | INTEGER  | FK → teams                         |
| away_team_id | INTEGER  | FK → teams                         |
| home_score   | INTEGER  | Placar mandante                    |
| away_score   | INTEGER  | Placar visitante                   |
| status       | TEXT     | "scheduled", "live", "finished"    |
| events       | JSON     | Lista de eventos: [{"minute": 23, "type": "goal", "team_id": 5, "description": "Gol de Gabigol"}] |
| started_at   | DATETIME | Início do jogo                     |
| finished_at  | DATETIME | Fim do jogo (nullable)             |

**Ciclo de vida dos matches:** jogos são cadastrados manualmente via `matches.json` (seed data com horários da rodada). O status transiciona automaticamente: `scheduled` → `live` quando `started_at` é atingido, `live` → `finished` após 120 minutos (margem para acréscimos). Eventos do jogo (gols, cartões) são inseridos manualmente ou via endpoint `POST /api/matches/{id}/events` durante o jogo.

### posts

| Coluna        | Tipo     | Descrição                                  |
|---------------|----------|--------------------------------------------|
| id            | INTEGER  | PK autoincrement                           |
| source        | TEXT     | "bluesky" ou "scraped"                     |
| external_id   | TEXT     | ID único na origem (UNIQUE)                |
| author_handle | TEXT     | Handle do autor                            |
| text          | TEXT     | Texto completo do post                     |
| team_id       | INTEGER  | FK → teams (nullable)                      |
| coach_id      | INTEGER  | FK → coaches (nullable)                    |
| match_id      | INTEGER  | FK → matches (nullable)                    |
| rage_score    | FLOAT    | Score de agressividade 0-10                |
| swear_words   | JSON     | Palavras detectadas ["pipoqueiro", "lixo"] |
| created_at    | DATETIME | Timestamp do post original                 |
| analyzed_at   | DATETIME | Quando foi processado                      |

### rage_snapshots

| Coluna          | Tipo     | Descrição                                       |
|-----------------|----------|-------------------------------------------------|
| id              | INTEGER  | PK autoincrement                                |
| team_id         | INTEGER  | FK → teams                                      |
| match_id        | INTEGER  | FK → matches (nullable)                         |
| round           | INTEGER  | Rodada (nullable)                               |
| period          | TEXT     | "minute", "match", "round", "season"            |
| post_count      | INTEGER  | Total de posts no período                        |
| avg_rage_score  | FLOAT    | Média de rage_score                              |
| max_rage_score  | FLOAT    | Pico de rage_score                               |
| top_swear_words | JSON     | {"pipoqueiro": 42, "juiz ladrão": 38}           |
| snapshot_at     | DATETIME | Timestamp do snapshot                            |

**Decisões:**
- `rage_snapshots` é atualizada a cada 30 segundos durante jogos ao vivo via `asyncio.create_task` com loop periódico (background task do FastAPI), evitando queries pesadas no SQLite
- `match_id` nullable em posts permite capturar xingamentos fora de horário de jogo
- `swear_words` em JSON para análise rápida sem JOIN adicional

## Dicionário de Xingamentos

### Estrutura do JSON

```json
{
  "terms": [
    {"word": "pipoqueiro", "level": 1, "weight": 2, "category": "frustração"},
    {"word": "juiz ladrão", "level": 2, "weight": 4, "category": "raiva"},
    {"word": "incompetente", "level": 2, "weight": 5, "category": "raiva"},
    {"word": "várzea", "level": 2, "weight": 3, "category": "raiva"}
  ]
}
```

### Níveis de Gravidade

| Nível | Nome       | Peso  | Exemplos                                       |
|-------|------------|-------|-------------------------------------------------|
| 1     | Frustração | 1-2   | "pipoqueiro", "vergonha", "entregou", "que fase"|
| 2     | Raiva      | 3-5   | "juiz ladrão", "roubaram", "fora [técnico]"     |
| 3     | Agressivo  | 6-8   | Palavrões direcionados, xingamentos pesados      |
| 4     | Nuclear    | 9-10  | Discurso de ódio, ameaças, preconceito           |

### Algoritmo de Pontuação

```python
def calculate_rage(post_text: str) -> float:
    words = normalize(post_text)  # lowercase, remove acentos
    matches = find_swear_words(words, DICTIONARY)

    if not matches:
        return 0.0

    # Score base: maior peso encontrado
    base = max(m.weight for m in matches)

    # Multiplicadores de intensidade
    if caps_ratio(post_text) > 0.5:     base *= 1.2   # CAPS LOCK
    if has_repeated_chars(post_text):    base *= 1.1   # "lixooooo"
    if exclamation_count(post_text) > 2: base *= 1.1   # "fora!!!"
    if len(matches) > 3:                base *= 1.3   # acúmulo

    return min(base, 10.0)  # clamp: multiplicadores podem ultrapassar 10, normaliza aqui
```

### Detecção de Alvo

1. **Busca por aliases** — normaliza o texto e busca matches contra `teams.json` e `coaches.json`
2. **Contexto de jogo** — se há jogo ao vivo e o post menciona termos genéricos ("time", "esse time"), associa ao time do jogo em andamento
3. **Desambiguação** — post que menciona 2 times: busca xingamento na mesma frase (split por pontuação) que contém o nome do time. Se ambos estão na mesma frase, associa ao time cujo nome/alias está mais próximo (menor distância em tokens) de um termo do dicionário

## Dashboard — Componentes

### Layout

Grid de 2 colunas:
- **Esquerda (2/3)**: Ranking de Times + Timeline de Raiva
- **Direita (1/3)**: Técnico Mais Xingado + Nuvem de Palavras + Feed ao Vivo

### Componentes

1. **Navbar** — Logo, "Brasileirão 2026", indicador AO VIVO, rodada atual, jogos em andamento
2. **RageRanking** — Barras horizontais ordenadas por avg_rage_score. Cada barra mostra: posição, nome do time, barra colorida (vermelho→amarelo→cinza), score numérico, contagem de posts. Filtro por rodada.
3. **RageTimeline** — Gráfico de linha (Recharts) mostrando rage_score agregado ao longo do tempo de um jogo. Anotações em eventos: gols, cartões, substituições. Eixo X = minutos do jogo (0'-90'+).
4. **TopCoach** — Card destacando o técnico com maior rage_score médio. Mostra: nome, time, score, top 3 palavras direcionadas a ele.
5. **WordCloud** — Palavras mais frequentes nos posts analisados. Tamanho proporcional à ocorrência. Cores por nível de gravidade.
6. **LiveFeed** — Lista scrollável dos últimos posts analisados. Cada item: handle, texto (censurado parcialmente), rage_score, time/técnico detectado. Atualiza via SSE.
7. **RoundFilter** — Dropdown para selecionar rodada. Altera todos os componentes simultaneamente.

### Comunicação Frontend ↔ Backend

- **Dados históricos**: REST calls normais (`fetch` / `axios`)
- **Live updates**: `EventSource` (SSE) em `/live/feed` para receber novos posts analisados
- **Agregações**: o frontend consome `rage_snapshots` já calculados, sem precisar agregar client-side

## API Endpoints

| Método | Rota                        | Descrição                                      |
|--------|-----------------------------|-------------------------------------------------|
| GET    | /api/rankings               | Ranking de times (query: round, limit)          |
| GET    | /api/rankings/coaches       | Ranking de técnicos                             |
| GET    | /api/timeline/{match_id}    | Dados temporais de rage para um jogo            |
| GET    | /api/stats/{team_id}        | Estatísticas detalhadas de um time              |
| GET    | /api/matches                | Lista de jogos (query: round, status)           |
| GET    | /api/rounds                 | Lista de rodadas disponíveis                    |
| GET    | /api/words                  | Top palavras (query: round, team_id)            |
| GET    | /api/live/feed              | SSE stream de posts analisados em tempo real    |
| GET    | /api/live/status            | Status da coleta (conectado, posts/min)         |
| POST   | /api/matches/{id}/events    | Adiciona evento ao jogo (gol, cartão, etc.)     |

### Formato SSE

Cada evento SSE em `/api/live/feed` envia JSON:

```json
{
  "type": "new_post",
  "data": {
    "id": 12345,
    "author_handle": "@torcedor",
    "text": "FORA TÉCNICO!!!",
    "team_id": 5,
    "team_name": "Corinthians",
    "coach_id": 3,
    "rage_score": 8.7,
    "swear_words": ["fora"],
    "created_at": "2026-04-15T21:32:05Z"
  }
}
```

Tipos de evento: `new_post`, `ranking_update` (a cada 30s com novo snapshot), `match_event` (gol, cartão).

## Configuração e Dados Iniciais

### teams.json

Todos os 20 times da Série A do Brasileirão com:
- Nome oficial, sigla, aliases (apelidos, abreviações, gírias)
- coach_id referenciando o técnico atual

### coaches.json

Técnicos dos 20 times com:
- Nome completo, apelidos conhecidos

### swear_dictionary.json

Dicionário curado com ~200 termos iniciais organizados por nível. Inclui:
- Xingamentos genéricos do futebol BR
- Termos específicos de torcidas
- Variações com caracteres especiais e abreviações

## Fora de Escopo (YAGNI)

- Autenticação de usuários
- Persistência em banco externo (Postgres, etc.)
- Bot Telegram/Discord
- Análise via LLM
- Deploy em cloud (foco em rodar local)
- Scraping de outras redes (Twitter/X, Reddit, etc.) — v1 foca apenas no Bluesky
- App mobile
