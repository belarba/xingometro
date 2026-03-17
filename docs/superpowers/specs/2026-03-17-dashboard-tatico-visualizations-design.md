# Dashboard Tatico - Creative Championship Visualizations

## Overview

Add 3 new creative visualizations to the Xingometro that cross-reference championship results with fan rage data. The approach ("Dashboard Tatico") combines one custom visual signature piece with two enhanced Recharts charts.

**Scope**: 3 new components, 2 new API endpoints, integration into existing tab system.

## Components

### 1. Escudo em Chamas (Shield on Fire)

A grid of all 20 Serie A teams where each team's visual intensity reflects their current rage score. Teams at peace appear calm; teams in crisis appear "on fire."

**Data sources** (existing endpoints):
- `GET /api/rankings` -> `avg_rage_score` per team
- `GET /api/matches?round=X` -> recent match scores

**Visual representation**:
- Each card shows: team `short_name` initials (styled), rage score, last match result
- Cards ordered by rage score (most "on fire" first)

**Rage intensity levels (CSS animations)**:

| Rage Score | Effect | Background |
|------------|--------|------------|
| 0-2 | Static, soft borders | gray/zinc tones |
| 2-4 | Gentle pulsing glow | yellow/amber |
| 4-6 | Stronger glow, animated shadow | orange |
| 6-8 | Strong pulsation, red glow | red |
| 8-10 | CSS shake + intense glow + animated gradient | red-to-orange gradient |

**Interactions**:
- Click -> opens existing `TeamDetailModal`
- Hover -> tooltip with rage score + recent result

**Layout**: Responsive grid - 5 cols desktop, 4 tablet, 2 mobile.

### 2. Scatter Plot "Derrota x Desespero" (Defeat x Despair)

A scatter chart revealing the correlation between match results and fan rage. Each dot is a team-match data point.

**Data source** (new endpoint):
- `GET /api/stats/correlation` -> returns list of:
  ```json
  {
    "match_id": 42,
    "team_name": "Corinthians",
    "short_name": "COR",
    "goal_diff": -2,
    "avg_rage": 8.7,
    "post_count": 156
  }
  ```
- `goal_diff`: goal difference from the team's perspective (positive = win)
- Derived from JOIN of Match + Post models, grouped by team per match

**Chart details**:
- X axis: goal difference (positive = victory, negative = defeat)
- Y axis: average rage score (0-10)
- Dot size: proportional to `post_count`
- Dot color: continuous rage scale (green -> yellow -> red)

**Quadrant labels** (humorous, via ReferenceLine + Label):

| Quadrant | Condition | Label |
|----------|-----------|-------|
| Top-left | Win + high rage | "Ganhou e ainda xingou!" |
| Top-right | Loss + high rage | "Perdeu e SURTOU" |
| Bottom-left | Win + low rage | "Ganhou tranquilo" |
| Bottom-right | Loss + low rage | "Perdeu e aceitou" |

**Interactions**:
- Hover tooltip: team name, match score, rage score, post count
- Filterable by round using existing `RoundFilter` component

**Implementation**: Recharts `ScatterChart` with custom tooltip and reference lines.

### 3. Montanha-Russa da Classificacao (Classification Roller Coaster)

A line chart showing a team's league position across rounds, with line color changing dynamically based on the rage score for each round.

**Data source** (new endpoint):
- `GET /api/stats/position-history?team_id=X` -> returns:
  ```json
  [
    { "round": 1, "position": 5, "avg_rage": 3.2, "result": "V", "score": "2x0" },
    { "round": 2, "position": 3, "avg_rage": 2.1, "result": "V", "score": "1x0" },
    { "round": 3, "position": 8, "avg_rage": 8.7, "result": "D", "score": "0x3" }
  ]
  ```
- Backend reconstructs standings round-by-round to calculate historical positions

**Chart details**:
- Y axis: inverted (position 1 at top, 20 at bottom) - natural for standings
- X axis: round numbers
- Line color per segment: changes based on rage score of that round
  - Green (0-3), Yellow (3-6), Orange (6-8), Red (8-10)
- Implementation: multiple overlapping `<Line>` segments or custom SVG via `<Customized>` since Recharts doesn't support per-segment colors natively

**Special markers**:
- Larger dot + icon when rage > 8 ("surto"/meltdown)
- Background reference areas for classification zones:
  - Positions 1-4: subtle blue (Libertadores)
  - Positions 5-6: subtle green (Sul-Americana)
  - Positions 17-20: subtle red (Relegation)

**Interactions**:
- Hover on points -> tooltip with: round, position, result, score, rage score
- Team selector dropdown (all 20 teams)
- Smooth animation on team switch (`animationDuration={500}`)

## New API Endpoints

### `GET /api/stats/correlation`

Returns per-team-per-match data for scatter plot visualization.

**Query params**: `round` (optional int) - filter to specific round

**Response**: Array of objects with `match_id`, `team_name`, `short_name`, `goal_diff`, `avg_rage`, `post_count`.

**Implementation**: SQL query joining `matches` and `posts` tables, grouping by team per match, calculating goal difference from team perspective and average rage score.

### `GET /api/stats/position-history`

Returns a team's classification position across all played rounds.

**Query params**: `team_id` (required int)

**Response**: Array of objects with `round`, `position`, `avg_rage`, `result` (V/E/D), `score`.

**Implementation**: For each completed round, reconstruct the standings table (points, goal difference, goals scored as tiebreakers) and determine the team's position. Also calculate average rage for that team in that round's matches.

## Integration

### Tab Structure
These 3 new components will live in a new sub-section of the existing "Xingometro" tab, below the current RageRanking + WordCloud + LiveFeed layout. They form a "Insights" section with their own header.

### Layout
```
[Existing Xingometro content]
─────────────────────────────
INSIGHTS
┌─────────────────────────────────────┐
│ Escudo em Chamas (full width)       │
├──────────────────┬──────────────────┤
│ Scatter Plot     │ Montanha-Russa   │
│ (half width)     │ (half width)     │
└──────────────────┴──────────────────┘
```

On mobile: all stack vertically (full width).

### New Frontend Types

```typescript
interface CorrelationEntry {
  match_id: number;
  team_name: string;
  short_name: string;
  goal_diff: number;
  avg_rage: number;
  post_count: number;
}

interface PositionHistoryEntry {
  round: number;
  position: number;
  avg_rage: number;
  result: "V" | "E" | "D";
  score: string;
}
```

### New API Functions (services/api.ts)

```typescript
fetchCorrelation(round?: number): Promise<CorrelationEntry[]>
fetchPositionHistory(teamId: number): Promise<PositionHistoryEntry[]>
```

## Technical Decisions

- **Escudo em Chamas**: Pure CSS animations (keyframes for shake, pulse, glow). No external animation library needed. Uses Tailwind's arbitrary values and `@keyframes` in index.css.
- **Scatter Plot**: Recharts `ScatterChart` - straightforward use of existing library.
- **Montanha-Russa**: Recharts `LineChart` with custom rendering. Per-segment coloring requires either:
  - (a) Multiple `<Line>` components, one per segment, clipped to their range
  - (b) Custom SVG path via `<Customized>` component
  - Recommend option (b) for cleaner output.
- **Position history calculation**: This is the most computationally expensive endpoint. Should be cached aggressively (standings don't change retroactively). Use same TTL-based caching pattern as the existing `/api/standings` endpoint.

## File Structure (new files)

```
frontend/src/components/
  ShieldGrid.tsx          # Escudo em Chamas
  CorrelationScatter.tsx  # Scatter Plot
  PositionRoller.tsx      # Montanha-Russa

backend/api/
  stats.py                # Add 2 new route handlers to existing file

frontend/src/types/
  index.ts                # Add 2 new interfaces

frontend/src/services/
  api.ts                  # Add 2 new fetch functions
```
