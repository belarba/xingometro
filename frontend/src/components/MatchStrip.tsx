import { useState, useEffect } from "react";
import { fetchMatches } from "../services/api";
import type { Match } from "../types";

interface MatchStripProps {
  round: number | null;
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);

  if (date.toDateString() === today.toDateString()) return "Hoje";
  if (date.toDateString() === tomorrow.toDateString()) return "Amanhã";
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export default function MatchStrip({ round }: MatchStripProps) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchMatches(round ?? undefined)
      .then((data) => {
        setMatches(data);
        setLoading(false);
      })
      .catch(() => {
        setMatches([]);
        setLoading(false);
      });
  }, [round]);

  if (loading) return null;
  if (matches.length === 0) return null;

  // Sort: live first, then scheduled, then finished
  const order = { live: 0, scheduled: 1, finished: 2 };
  const sorted = [...matches].sort(
    (a, b) => (order[a.status as keyof typeof order] ?? 3) - (order[b.status as keyof typeof order] ?? 3)
  );

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3 overflow-x-auto">
      <div className="flex gap-3 min-w-max">
        {sorted.map((m) => (
          <div
            key={m.id}
            className={`min-w-[150px] rounded-lg p-2 text-center border ${
              m.status === "live"
                ? "bg-red-500/[0.08] border-red-500/20"
                : "bg-white/[0.02] border-white/[0.06]"
            } ${m.status === "finished" ? "opacity-60" : ""}`}
          >
            {m.status === "live" && (
              <div className="text-[10px] font-semibold text-red-500">AO VIVO</div>
            )}
            {m.status === "scheduled" && m.started_at && (
              <div className="text-[10px] text-gray-500">
                {formatDate(m.started_at)} {formatTime(m.started_at)}
              </div>
            )}
            {m.status === "finished" && (
              <div className="text-[10px] text-green-500">Encerrado</div>
            )}
            <div className="text-xs mt-1">
              {m.home_short_name || m.home_team_name}{" "}
              {m.status !== "scheduled" ? (
                <span className="font-bold">{m.home_score} × {m.away_score}</span>
              ) : (
                <span className="text-gray-500">×</span>
              )}{" "}
              {m.away_short_name || m.away_team_name}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
