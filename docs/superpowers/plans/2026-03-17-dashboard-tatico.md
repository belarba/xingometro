# Dashboard Tatico Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 creative visualizations (ShieldGrid, CorrelationScatter, PositionRoller) that cross-reference championship results with fan rage data.

**Architecture:** Two new backend endpoints added to the existing `stats.py` router, feeding data to 3 new React components integrated into the "Xingometro" tab's new "Insights" section. CSS keyframe animations for the ShieldGrid signature piece; Recharts for the two chart components.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), React 18/TypeScript/Recharts/Tailwind CSS (frontend)

**Spec:** `docs/superpowers/specs/2026-03-17-dashboard-tatico-visualizations-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/src/types/index.ts` | Add `CorrelationEntry` and `PositionHistoryEntry` interfaces |
| Modify | `frontend/src/services/api.ts` | Add `fetchCorrelation()` and `fetchPositionHistory()` functions |
| Modify | `backend/api/stats.py` | Add `/stats/correlation` and `/stats/position-history/{team_id}` endpoints |
| Create | `frontend/src/components/ShieldGrid.tsx` | Escudo em Chamas grid component |
| Create | `frontend/src/components/CorrelationScatter.tsx` | Scatter plot component |
| Create | `frontend/src/components/PositionRoller.tsx` | Position history line chart component |
| Modify | `frontend/src/index.css` | Add CSS keyframe animations for ShieldGrid |
| Modify | `frontend/src/App.tsx` | Integrate 3 components into Insights section |

## Chunk 1: Backend Endpoints + Frontend Types/API

### Task 1: Add frontend types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add CorrelationEntry and PositionHistoryEntry interfaces**

Add at the end of `frontend/src/types/index.ts`:

```typescript
export interface CorrelationEntry {
  match_id: number;
  team_id: number;
  team_name: string;
  short_name: string;
  goal_diff: number;
  avg_rage_score: number;
  post_count: number;
}

// result: V = Vitoria (win), E = Empate (draw), D = Derrota (loss)
export interface PositionHistoryEntry {
  round: number;
  position: number;
  avg_rage_score: number;
  result: "V" | "E" | "D";
  score: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add CorrelationEntry and PositionHistoryEntry types"
```

### Task 2: Add frontend API functions

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Add import for new types**

Add `CorrelationEntry` and `PositionHistoryEntry` to the import block at the top of `frontend/src/services/api.ts`:

```typescript
import type {
  RankingEntry,
  CoachRanking,
  TimelinePoint,
  Match,
  WordEntry,
  LiveStatus,
  TeamStats,
  StandingEntry,
  CorrelationEntry,
  PositionHistoryEntry,
} from "../types";
```

- [ ] **Step 2: Add fetchCorrelation function**

Add at the end of `frontend/src/services/api.ts`:

```typescript
export async function fetchCorrelation(round?: number): Promise<CorrelationEntry[]> {
  const res = await fetch(`/api/stats/correlation${buildParams({ round })}`);
  if (!res.ok) throw new Error("Failed to fetch correlation data");
  return res.json();
}
```

- [ ] **Step 3: Add fetchPositionHistory function**

Add after `fetchCorrelation`:

```typescript
export async function fetchPositionHistory(teamId: number): Promise<PositionHistoryEntry[]> {
  const res = await fetch(`/api/stats/position-history/${teamId}`);
  if (!res.ok) throw new Error("Failed to fetch position history");
  return res.json();
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add fetchCorrelation and fetchPositionHistory API functions"
```

### Task 3: Add correlation endpoint

**Files:**
- Modify: `backend/api/stats.py`

- [ ] **Step 1: Add Match import**

Add at the top of `backend/api/stats.py`, after existing imports:

```python
from backend.models.match import Match
```

Note: `Match` is already imported inside `get_top_words` via a local import. Move it to the top-level imports and remove the `from backend.models.match import Match` line inside `get_top_words` (around line 65 of the original file).

- [ ] **Step 2: Add the correlation endpoint**

Add after the `get_top_words` function in `backend/api/stats.py`:

```python
@router.get("/stats/correlation")
def get_correlation(
    round_num: Optional[int] = Query(None, alias="round"),
    db: Session = Depends(get_db),
):
    """Per-team-per-match correlation between goal diff and rage score."""
    # Get all finished matches, optionally filtered by round
    match_query = db.query(Match).filter(Match.status == "finished")
    if round_num is not None:
        match_query = match_query.filter(Match.round == round_num)
    matches = match_query.all()

    results = []
    for match in matches:
        # Process each team in the match (home and away)
        for is_home in [True, False]:
            team_id = match.home_team_id if is_home else match.away_team_id

            # Calculate goal diff from this team's perspective
            if is_home:
                goal_diff = match.home_score - match.away_score
            else:
                goal_diff = match.away_score - match.home_score

            # Get rage stats for this team in this match
            post_stats = (
                db.query(
                    func.count(Post.id).label("post_count"),
                    func.avg(Post.rage_score).label("avg_rage"),
                )
                .filter(
                    Post.match_id == match.id,
                    Post.team_id == team_id,
                    Post.team_id.isnot(None),
                    Post.match_id.isnot(None),
                )
                .first()
            )

            post_count = post_stats.post_count or 0
            if post_count == 0:
                continue

            team = db.query(Team).filter(Team.id == team_id).first()
            if not team:
                continue

            results.append({
                "match_id": match.id,
                "team_id": team_id,
                "team_name": team.name,
                "short_name": team.short_name,
                "goal_diff": goal_diff,
                "avg_rage_score": round(post_stats.avg_rage or 0, 1),
                "post_count": post_count,
            })

    return results
```

- [ ] **Step 3: Verify the endpoint loads**

Run: `cd backend && python -c "from backend.api.stats import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/api/stats.py
git commit -m "feat: add /stats/correlation endpoint"
```

### Task 4: Add position-history endpoint

**Files:**
- Modify: `backend/api/stats.py`

- [ ] **Step 1: Add TTL cache for position history**

Add after the existing imports at the top of `backend/api/stats.py`:

```python
import time

# Cache for position history (expensive computation)
_position_cache: dict[int, dict] = {}
_POSITION_CACHE_TTL = 300  # 5 minutes
```

- [ ] **Step 2: Add the position-history endpoint**

Add after the `get_correlation` function:

```python
@router.get("/stats/position-history/{team_id}")
def get_position_history(team_id: int, db: Session = Depends(get_db)):
    """Team's league position across rounds with rage data."""
    from fastapi import HTTPException

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
```

- [ ] **Step 3: Verify the endpoint loads**

Run: `cd backend && python -c "from backend.api.stats import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/api/stats.py
git commit -m "feat: add /stats/position-history/{team_id} endpoint with TTL cache"
```

## Chunk 2: ShieldGrid Component

### Task 5: Add CSS keyframe animations

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add keyframe animations for ShieldGrid**

Add at the end of `frontend/src/index.css`:

```css
/* ShieldGrid animations */
@keyframes shield-pulse {
  0%, 100% { box-shadow: 0 0 8px 0 currentColor; }
  50% { box-shadow: 0 0 20px 4px currentColor; }
}

@keyframes shield-pulse-strong {
  0%, 100% { box-shadow: 0 0 12px 2px currentColor; }
  50% { box-shadow: 0 0 28px 8px currentColor; }
}

@keyframes shield-shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-2px); }
  20%, 40%, 60%, 80% { transform: translateX(2px); }
}

@keyframes shield-gradient {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.shield-pulse {
  animation: shield-pulse 2s ease-in-out infinite;
}

.shield-pulse-strong {
  animation: shield-pulse-strong 1.5s ease-in-out infinite;
}

.shield-shake {
  animation: shield-shake 0.6s ease-in-out infinite, shield-pulse-strong 1.5s ease-in-out infinite;
}

.shield-gradient-bg {
  background: linear-gradient(270deg, #ef4444, #f97316, #ef4444);
  background-size: 200% 200%;
  animation: shield-gradient 3s ease infinite;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: add CSS keyframe animations for ShieldGrid"
```

### Task 6: Create ShieldGrid component

**Files:**
- Create: `frontend/src/components/ShieldGrid.tsx`

- [ ] **Step 1: Create the ShieldGrid component**

Create `frontend/src/components/ShieldGrid.tsx`:

```typescript
import { useState } from "react";
import type { RankingEntry, Match } from "../types";
import TeamDetailModal from "./TeamDetailModal";

interface ShieldGridProps {
  rankings: RankingEntry[];
  matches: Match[];
}

function getRageLevel(score: number) {
  if (score >= 8) return { class: "shield-shake shield-gradient-bg", color: "text-red-400", border: "border-red-500/60" };
  if (score >= 6) return { class: "shield-pulse-strong", color: "text-red-400", border: "border-red-500/40" };
  if (score >= 4) return { class: "shield-pulse", color: "text-orange-400", border: "border-orange-500/40" };
  if (score >= 2) return { class: "", color: "text-yellow-400", border: "border-yellow-500/30" };
  return { class: "", color: "text-gray-400", border: "border-white/[0.08]" };
}

function getGlowColor(score: number): string {
  if (score >= 8) return "rgba(239, 68, 68, 0.6)";
  if (score >= 6) return "rgba(239, 68, 68, 0.3)";
  if (score >= 4) return "rgba(249, 115, 22, 0.25)";
  if (score >= 2) return "rgba(234, 179, 8, 0.15)";
  return "transparent";
}

function findLastMatch(teamId: number, matches: Match[]): Match | null {
  const teamMatches = matches.filter(
    (m) => (m.home_team_id === teamId || m.away_team_id === teamId) && m.status === "finished"
  );
  return teamMatches.length > 0 ? teamMatches[teamMatches.length - 1] : null;
}

function formatScore(teamId: number, match: Match): string {
  const isHome = match.home_team_id === teamId;
  const gf = isHome ? match.home_score : match.away_score;
  const ga = isHome ? match.away_score : match.home_score;
  return `${gf}x${ga}`;
}

export default function ShieldGrid({ rankings, matches }: ShieldGridProps) {
  const [selectedTeam, setSelectedTeam] = useState<RankingEntry | null>(null);

  const sorted = [...rankings].sort((a, b) => b.avg_rage_score - a.avg_rage_score);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">Escudos em Chamas</h2>

      {sorted.length === 0 ? (
        <p className="text-gray-500 text-sm">
          Dados aparecerao quando partidas forem jogadas e posts coletados.
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
          {sorted.map((entry) => {
            const level = getRageLevel(entry.avg_rage_score);
            const lastMatch = findLastMatch(entry.team_id, matches);

            return (
              <div
                key={entry.team_id}
                className={`relative flex flex-col items-center justify-center p-4 rounded-xl border cursor-pointer transition-colors hover:bg-white/[0.05] ${level.border} ${level.class}`}
                style={{ color: getGlowColor(entry.avg_rage_score) }}
                onClick={() => setSelectedTeam(entry)}
                title={`${entry.team_name} - Raiva: ${entry.avg_rage_score.toFixed(1)}`}
              >
                <span className="text-xl font-black text-white tracking-tight">
                  {entry.short_name}
                </span>
                <span className={`text-sm font-bold mt-1 ${level.color}`}>
                  {entry.avg_rage_score.toFixed(1)}
                </span>
                {lastMatch && (
                  <span className="text-xs text-gray-500 mt-0.5">
                    {formatScore(entry.team_id, lastMatch)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {selectedTeam && (
        <TeamDetailModal
          teamId={selectedTeam.team_id}
          teamName={selectedTeam.team_name}
          shortName={selectedTeam.short_name}
          onClose={() => setSelectedTeam(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ShieldGrid.tsx
git commit -m "feat: add ShieldGrid (Escudo em Chamas) component"
```

## Chunk 3: CorrelationScatter Component

### Task 7: Create CorrelationScatter component

**Files:**
- Create: `frontend/src/components/CorrelationScatter.tsx`

- [ ] **Step 1: Create the CorrelationScatter component**

Create `frontend/src/components/CorrelationScatter.tsx`:

```typescript
import { useState, useEffect, useCallback } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { CorrelationEntry } from "../types";
import { fetchCorrelation } from "../services/api";
import TeamDetailModal from "./TeamDetailModal";

interface CorrelationScatterProps {
  round: number | null;
}

function getRageColor(score: number): string {
  if (score >= 7) return "#ef4444";
  if (score >= 4) return "#f97316";
  if (score >= 2) return "#eab308";
  return "#6b7280";
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: CorrelationEntry }>;
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#1a1a2e] border border-white/10 rounded-lg px-3 py-2 text-sm">
      <div className="font-bold">{d.team_name}</div>
      <div className="text-gray-400">
        Saldo: {d.goal_diff > 0 ? "+" : ""}{d.goal_diff} | Raiva: {d.avg_rage_score.toFixed(1)}
      </div>
      <div className="text-gray-500 text-xs">{d.post_count} posts</div>
    </div>
  );
}

export default function CorrelationScatter({ round }: CorrelationScatterProps) {
  const [data, setData] = useState<CorrelationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<CorrelationEntry | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(false);
    fetchCorrelation(round ?? undefined)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [round]);

  useEffect(() => { load(); }, [load]);

  const maxPosts = data.length > 0 ? Math.max(...data.map((d) => d.post_count)) : 1;

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">Derrota x Desespero</h2>

      {loading ? (
        <div className="h-64 bg-white/[0.02] rounded-lg animate-pulse" />
      ) : error ? (
        <div className="h-64 flex flex-col items-center justify-center gap-2">
          <p className="text-gray-500 text-sm">Erro ao carregar dados</p>
          <button onClick={load} className="text-xs text-orange-400 hover:underline">
            Tentar novamente
          </button>
        </div>
      ) : data.length === 0 ? (
        <p className="text-gray-500 text-sm">
          Dados aparecerao quando partidas forem jogadas e posts coletados.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              type="number"
              dataKey="goal_diff"
              name="Saldo"
              tick={{ fill: "#9ca3af", fontSize: 12 }}
              stroke="rgba(255,255,255,0.1)"
            />
            <YAxis
              type="number"
              dataKey="avg_rage_score"
              name="Raiva"
              domain={[0, 10]}
              tick={{ fill: "#9ca3af", fontSize: 12 }}
              stroke="rgba(255,255,255,0.1)"
            />

            {/* Quadrant reference lines */}
            <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
            <ReferenceLine y={5} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />

            <Tooltip content={<CustomTooltip />} />

            <Scatter
              data={data}
              onClick={(_data, _index, event) => {
                // Recharts passes (data, index, event) — data contains the payload
                const entry = _data as unknown as { payload: CorrelationEntry };
                if (entry?.payload) setSelectedTeam(entry.payload);
              }}
              cursor="pointer"
            >
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={getRageColor(entry.avg_rage_score)}
                  r={Math.max(4, (entry.post_count / maxPosts) * 16)}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      )}

      {/* Quadrant labels */}
      {!loading && !error && data.length > 0 && (
        <div className="grid grid-cols-2 gap-2 mt-2 text-center text-xs text-gray-500">
          <span>Perdeu e SURTOU</span>
          <span>Ganhou e ainda xingou!</span>
          <span>Perdeu e aceitou</span>
          <span>Ganhou tranquilo</span>
        </div>
      )}

      {selectedTeam && (
        <TeamDetailModal
          teamId={selectedTeam.team_id}
          teamName={selectedTeam.team_name}
          shortName={selectedTeam.short_name}
          onClose={() => setSelectedTeam(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CorrelationScatter.tsx
git commit -m "feat: add CorrelationScatter (Derrota x Desespero) component"
```

## Chunk 4: PositionRoller Component

### Task 8: Create PositionRoller component

**Files:**
- Create: `frontend/src/components/PositionRoller.tsx`

- [ ] **Step 1: Create the PositionRoller component**

Create `frontend/src/components/PositionRoller.tsx`:

```typescript
import { useState, useEffect, useCallback } from "react";
import {
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ResponsiveContainer,
  Customized,
} from "recharts";
import type { PositionHistoryEntry, RankingEntry } from "../types";
import { fetchPositionHistory } from "../services/api";

interface PositionRollerProps {
  rankings: RankingEntry[];
}

function getRageSegmentColor(score: number): string {
  if (score >= 8) return "#ef4444";
  if (score >= 6) return "#f97316";
  if (score >= 3) return "#eab308";
  return "#22c55e";
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: PositionHistoryEntry }>;
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const resultMap = { V: "Vitoria", E: "Empate", D: "Derrota" };
  return (
    <div className="bg-[#1a1a2e] border border-white/10 rounded-lg px-3 py-2 text-sm">
      <div className="font-bold">Rodada {d.round}</div>
      <div className="text-gray-300">{d.position}a posicao</div>
      <div className="text-gray-400">{resultMap[d.result]} ({d.score})</div>
      <div className="text-gray-500 text-xs">Raiva: {d.avg_rage_score.toFixed(1)}</div>
    </div>
  );
}

/**
 * Custom SVG renderer for per-segment colored line + dots.
 * Uses Recharts <Customized> to draw directly on the SVG canvas.
 * Each segment between two data points gets colored by the destination point's rage score.
 */
function ColoredPath({ formattedGraphicalItems, data }: { formattedGraphicalItems?: unknown[]; data: PositionHistoryEntry[] }) {
  // Access the line's rendered points from Recharts internals
  const firstSeries = formattedGraphicalItems?.[0] as { props?: { points?: Array<{ x: number; y: number }> } } | undefined;
  const points = firstSeries?.props?.points;
  if (!points || points.length === 0) return null;

  return (
    <g>
      {/* Line segments colored by rage */}
      {points.map((point, i) => {
        if (i === 0) return null;
        const prev = points[i - 1];
        const entry = data[i];
        return (
          <line
            key={`seg-${i}`}
            x1={prev.x}
            y1={prev.y}
            x2={point.x}
            y2={point.y}
            stroke={getRageSegmentColor(entry?.avg_rage_score ?? 0)}
            strokeWidth={2}
          />
        );
      })}
      {/* Dots */}
      {points.map((point, i) => {
        const entry = data[i];
        if (!entry) return null;
        const isSurto = entry.avg_rage_score >= 8;
        return (
          <circle
            key={`dot-${i}`}
            cx={point.x}
            cy={point.y}
            r={isSurto ? 6 : 3}
            fill={getRageSegmentColor(entry.avg_rage_score)}
            stroke={isSurto ? "#fff" : "none"}
            strokeWidth={isSurto ? 2 : 0}
          />
        );
      })}
    </g>
  );
}

export default function PositionRoller({ rankings }: PositionRollerProps) {
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [data, setData] = useState<PositionHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  // Auto-select first team
  useEffect(() => {
    if (rankings.length > 0 && selectedTeamId === null) {
      setSelectedTeamId(rankings[0].team_id);
    }
  }, [rankings, selectedTeamId]);

  const load = useCallback(() => {
    if (selectedTeamId === null) return;
    setLoading(true);
    setError(false);
    fetchPositionHistory(selectedTeamId)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [selectedTeamId]);

  useEffect(() => { load(); }, [load]);

  const selectedTeam = rankings.find((r) => r.team_id === selectedTeamId);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Montanha-Russa</h2>
        <select
          value={selectedTeamId ?? ""}
          onChange={(e) => setSelectedTeamId(Number(e.target.value))}
          className="bg-white/[0.05] border border-white/[0.1] rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-white/20"
        >
          {rankings.map((r) => (
            <option key={r.team_id} value={r.team_id}>
              {r.short_name || r.team_name}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="h-64 bg-white/[0.02] rounded-lg animate-pulse" />
      ) : error ? (
        <div className="h-64 flex flex-col items-center justify-center gap-2">
          <p className="text-gray-500 text-sm">Erro ao carregar dados</p>
          <button onClick={load} className="text-xs text-orange-400 hover:underline">
            Tentar novamente
          </button>
        </div>
      ) : data.length === 0 ? (
        <p className="text-gray-500 text-sm">
          {selectedTeam
            ? `Sem historico de posicao para ${selectedTeam.short_name || selectedTeam.team_name}.`
            : "Selecione um time."}
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />

            {/* Classification zones */}
            <ReferenceArea y1={1} y2={4} fill="rgba(59,130,246,0.06)" />
            <ReferenceArea y1={5} y2={6} fill="rgba(34,197,94,0.06)" />
            <ReferenceArea y1={17} y2={20} fill="rgba(239,68,68,0.06)" />

            <XAxis
              dataKey="round"
              tick={{ fill: "#9ca3af", fontSize: 12 }}
              stroke="rgba(255,255,255,0.1)"
            />
            <YAxis
              reversed
              domain={[1, 20]}
              tick={{ fill: "#9ca3af", fontSize: 12 }}
              stroke="rgba(255,255,255,0.1)"
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Hidden line to provide data points for Customized; actual rendering in ColoredPath */}
            {/* We need a Line for Recharts to compute point positions used by Customized */}
            <Customized component={(props: Record<string, unknown>) => <ColoredPath {...props} data={data} />} />
          </LineChart>
        </ResponsiveContainer>
      )}

      {/* Zone legend */}
      {!loading && !error && data.length > 0 && (
        <div className="flex gap-4 mt-2 text-xs text-gray-500 justify-center">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500/40" /> Libertadores
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500/40" /> Sul-Americana
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500/40" /> Rebaixamento
          </span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PositionRoller.tsx
git commit -m "feat: add PositionRoller (Montanha-Russa) component"
```

## Chunk 5: Integration into App.tsx

### Task 9: Wire up components in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add imports for new components and fetchMatches**

Add to the imports section of `frontend/src/App.tsx`:

```typescript
import ShieldGrid from "./components/ShieldGrid";
import CorrelationScatter from "./components/CorrelationScatter";
import PositionRoller from "./components/PositionRoller";
```

Also add `fetchMatches` to the existing import from `"./services/api"`:

```typescript
import { fetchCoachRankings, fetchLiveStatus, fetchMatches } from "./services/api";
```

And add `Match` to the types import:

```typescript
import type { CoachRanking, LiveStatus, Match } from "./types";
```

- [ ] **Step 2: Add matches state and fetch**

Inside `App()`, after the `liveStatus` state declaration, add:

```typescript
const [matches, setMatches] = useState<Match[]>([]);
```

And add a new `useEffect` after the coach rankings one:

```typescript
// Fetch matches for ShieldGrid
useEffect(() => {
  fetchMatches(selectedRound ?? undefined)
    .then(setMatches)
    .catch(() => setMatches([]));
}, [selectedRound]);
```

- [ ] **Step 3: Add the Insights section to the xingometro tab**

In the JSX, after the existing `</div>` that closes the `grid grid-cols-1 lg:grid-cols-[2fr_1fr]` div inside the `activeTab === "xingometro"` branch, add:

```tsx
{/* Insights section */}
<div className="mt-8">
  <h2 className="text-xl font-bold mb-4 text-gray-300">Insights</h2>
  <div className="space-y-4">
    <ShieldGrid rankings={rankings} matches={matches} />
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <CorrelationScatter round={selectedRound} />
      <PositionRoller rankings={rankings} />
    </div>
  </div>
</div>
```

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 5: Run the dev server and verify visually**

Run: `cd frontend && npm run dev`
Verify: All 3 new components render in the Insights section below the existing content.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire up Insights section with ShieldGrid, CorrelationScatter, PositionRoller"
```
