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
