import { useState, useEffect, useCallback } from "react";
import {
  LineChart,
  Line,
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

            {/* Hidden Line provides computed point positions to Customized via formattedGraphicalItems */}
            <Line
              type="monotone"
              dataKey="position"
              stroke="transparent"
              dot={false}
              activeDot={false}
              isAnimationActive={false}
            />
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
