import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import type { Match, TimelinePoint, MatchEvent } from "../types";
import { fetchTimeline, fetchMatches } from "../services/api";

interface RageTimelineProps {
  matchId: number | null;
  round: number | null;
}

function eventEmoji(type: string): string {
  if (type === "goal") return "\u26BD";
  if (type === "red_card") return "\uD83D\uDFE5";
  if (type === "yellow_card") return "\uD83D\uDFE8";
  return "\u2022";
}

export default function RageTimeline({ matchId: externalMatchId, round }: RageTimelineProps) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(
    externalMatchId
  );
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [events, setEvents] = useState<MatchEvent[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch matches for selector
  useEffect(() => {
    fetchMatches(round ?? undefined)
      .then((data) => {
        setMatches(data);
        if (data.length > 0 && selectedMatchId === null) {
          setSelectedMatchId(data[0].id);
        }
      })
      .catch(() => {});
  }, [round]);

  // Sync external matchId
  useEffect(() => {
    if (externalMatchId !== null) {
      setSelectedMatchId(externalMatchId);
    }
  }, [externalMatchId]);

  // Fetch timeline when match changes
  useEffect(() => {
    if (selectedMatchId === null) return;

    setLoading(true);
    fetchTimeline(selectedMatchId)
      .then((data) => {
        setTimeline(data.points || []);
        setEvents(data.events || []);
      })
      .catch(() => {
        setTimeline([]);
        setEvents([]);
      })
      .finally(() => setLoading(false));
  }, [selectedMatchId, matches]);

  const selectedMatch = matches.find((m) => m.id === selectedMatchId);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Timeline de Raiva</h2>

        <select
          value={selectedMatchId ?? ""}
          onChange={(e) =>
            setSelectedMatchId(e.target.value ? Number(e.target.value) : null)
          }
          className="bg-white/[0.05] border border-white/[0.1] rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-white/20"
        >
          <option value="">Selecione um jogo</option>
          {matches.map((m) => (
            <option key={m.id} value={m.id}>
              {m.home_team_name} {m.home_score} x {m.away_score}{" "}
              {m.away_team_name}
            </option>
          ))}
        </select>
      </div>

      {selectedMatch && (
        <p className="text-xs text-gray-500 mb-3">
          {selectedMatch.home_team_name} {selectedMatch.home_score} x{" "}
          {selectedMatch.away_score} {selectedMatch.away_team_name}
          {selectedMatch.status === "live" && (
            <span className="ml-2 text-red-500 font-semibold">AO VIVO</span>
          )}
        </p>
      )}

      {loading ? (
        <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
          Carregando...
        </div>
      ) : timeline.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
          Nenhum dado disponivel
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={timeline}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="minute"
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              domain={[0, 90]}
            />
            <YAxis
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              domain={[0, 10]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1a1a2e",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "8px",
                color: "#fff",
                fontSize: "12px",
              }}
              formatter={(value) => [
                typeof value === "number" ? (value as number).toFixed(2) : "0",
                "Raiva",
              ]}
              labelFormatter={(label) => `Minuto ${label}`}
            />
            <Line
              type="monotone"
              dataKey="avg_rage_score"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#ef4444" }}
            />

            {events.map((evt, i) => {
              const point = timeline.find((t) => t.minute === evt.minute);
              if (!point) return null;
              return (
                <ReferenceDot
                  key={i}
                  x={evt.minute}
                  y={point.avg_rage_score}
                  r={6}
                  fill="transparent"
                  stroke="transparent"
                  label={{
                    value: eventEmoji(evt.type),
                    position: "top",
                    fontSize: 16,
                  }}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
