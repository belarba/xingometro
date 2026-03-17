# Classificação do Brasileirão + Próximos Jogos

## Resumo

Adicionar ao Xingômetro duas funcionalidades: (1) tabela de classificação do Brasileirão Série A e (2) exibição de próximos jogos / jogos ao vivo. Navegação via tabs no topo (Xingômetro | Classificação).

## Decisões de design

- **Fonte de dados:** Football-Data.org API (já integrada no backend via `FootballAPICollector`)
- **Navegação:** Tabs abaixo da Navbar — "Xingômetro" e "Classificação"
- **Próximos jogos:** Faixa compacta na tab Xingômetro + lista completa na tab Classificação
- **Tabela:** Completa com Pos, Time, P, J, V, E, D, GP, GC, SG + zonas coloridas

## Backend

### Novo endpoint: `GET /api/standings`

Busca standings da Football-Data.org `competitions/BSA/standings` e retorna a tabela total (type TOTAL).

**Response:**
```json
[
  {
    "position": 1,
    "team_id": 5,
    "team_name": "Flamengo",
    "short_name": "FLA",
    "played_games": 5,
    "won": 5,
    "draw": 0,
    "lost": 0,
    "goals_for": 12,
    "goals_against": 3,
    "goal_difference": 9,
    "points": 15
  }
]
```

**Implementação:**
- Novo arquivo `backend/api/standings.py` com router
- Faz request à Football-Data.org `competitions/BSA/standings`
- Resolve `team_id` e `short_name` usando a tabela local de teams (mesma lógica de `_resolve_team` do collector)
- Cache em memória de 30 minutos (standings não mudam durante jogos)
- Registrar router no app principal

### Alteração no endpoint: `GET /api/matches`

Já suporta filtro por `round` e `status`. Adicionar `home_short_name` e `away_short_name` na response para uso no `MatchStrip` (siglas dos times).

### Utilitário compartilhado: resolução de times

Extrair a lógica de resolução de nome de time → `team_id` para um módulo compartilhado (`backend/utils/team_resolver.py`) que pode ser usado tanto pelo `FootballAPICollector` quanto pelo novo endpoint de standings. Faz lookup por nome/alias na tabela `teams` do banco.

### Cache

O endpoint `/api/standings` usa cache TTL simples em memória (dict + timestamp). TTL de 30 minutos. Assume single-worker (uvicorn sem múltiplos workers). Cache não sobrevive restart — primeira request após restart faz call à API externa. Se a API externa falhar, retorna 503.

## Frontend

### Tipos novos (`types/index.ts`)

```typescript
interface StandingEntry {
  position: number;
  team_id: number;
  team_name: string;
  short_name: string;
  played_games: number;
  won: number;
  draw: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}
```

### Novo service (`services/api.ts`)

```typescript
fetchStandings(): Promise<StandingEntry[]>
```

### Componentes novos

#### `TabNav.tsx`
- Duas tabs: "Xingômetro" e "Classificação"
- Estado controlado no `App.tsx`
- Posicionado abaixo da Navbar, acima do conteúdo

#### `MatchStrip.tsx`
- Faixa horizontal scrollável no topo da tab Xingômetro
- Cards compactos por jogo:
  - Ao vivo: badge vermelho + placar + minuto
  - Próximo: horário + siglas dos times
  - Encerrado: placar final (opacidade reduzida)
- Filtra pela rodada selecionada
- Usa `fetchMatches(round)`

#### `StandingsTable.tsx`
- Tabela de classificação completa
- Colunas: #, Time, P, J, V, E, D, GP, GC, SG
- Zonas de cor na borda esquerda:
  - Posições 1-4: azul (Libertadores)
  - Posições 5-6: verde (Sul-Americana)
  - Posições 17-20: vermelho (Rebaixamento)
- Saldo de gols: verde se positivo, vermelho se negativo
- Legenda abaixo da tabela
- Usa `fetchStandings()`

#### `MatchList.tsx`
- Lista vertical de jogos da rodada (coluna lateral na tab Classificação)
- Cards maiores que o MatchStrip, com nomes completos dos times
- Agrupados: ao vivo primeiro, depois futuros, depois encerrados
- Ao vivo: borda/fundo vermelho sutil
- Usa `fetchMatches(round)`

### Estados de loading/erro/vazio

Todos os componentes novos seguem o padrão existente no app:
- **Loading:** texto "Carregando..." (consistente com outros componentes)
- **Erro:** texto "Erro ao carregar dados" com retry automático
- **Vazio:** `MatchStrip`/`MatchList` — "Nenhum jogo na rodada"; `StandingsTable` — "Classificação indisponível"

### Alterações em componentes existentes

#### `App.tsx`
- Adiciona estado `activeTab: "xingometro" | "classificacao"`
- Renderiza `TabNav` abaixo da Navbar
- `RoundFilter` visível em ambas as tabs — controla a rodada para `MatchStrip` e `MatchList`. A `StandingsTable` mostra sempre a classificação geral (não depende da rodada).
- Renderiza conteúdo conforme tab ativa:
  - Xingômetro: `MatchStrip` + layout atual (RageRanking, Timeline, etc.)
  - Classificação: `StandingsTable` + `MatchList` em grid 2/3 + 1/3

#### `types/index.ts`
- Adicionar `home_short_name` e `away_short_name` ao tipo `Match`

## Fluxo de dados

```
Football-Data.org API
    ↓
GET /api/standings (cache 30min)
    ↓
fetchStandings() → StandingsTable

GET /api/matches?round=X
    ↓
fetchMatches() → MatchStrip (tab Xingômetro)
               → MatchList (tab Classificação)
```

## Responsividade

- Desktop: tabela + jogos lado a lado (grid 2fr 1fr)
- Mobile: stack vertical — tabela acima, jogos abaixo
- MatchStrip: scroll horizontal em telas pequenas

## Fora de escopo

- Clicar num jogo para ver detalhes/timeline (pode ser futuro)
- Histórico de classificação por rodada
- Logos/escudos dos times (Football-Data.org retorna `crest` URL mas não usaremos nesta versão)
- Zonas de classificação dinâmicas (usamos posições fixas simplificadas: 1-4 Libertadores, 5-6 Sul-Americana, 17-20 Rebaixamento)
