import { useState, useEffect } from "react";
import { fetchMatches } from "../services/api";
import type { Match } from "../types";

interface MatchListProps {
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
  return date.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
}

export default function MatchList({ round }: MatchListProps) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetchMatches(round ?? undefined)
      .then((data) => {
        setMatches(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setMatches([]);
        setLoading(false);
      });
  }, [round]);

  // Sort: live first, then scheduled, then finished
  const order = { live: 0, scheduled: 1, finished: 2 };
  const sorted = [...matches].sort(
    (a, b) => (order[a.status as keyof typeof order] ?? 3) - (order[b.status as keyof typeof order] ?? 3)
  );

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">
        {round ? `Rodada ${round}` : "Jogos"}
      </h2>

      {loading ? (
        <p className="text-gray-500 text-sm">Carregando...</p>
      ) : error ? (
        <p className="text-gray-500 text-sm">Erro ao carregar dados</p>
      ) : sorted.length === 0 ? (
        <p className="text-gray-500 text-sm">Nenhum jogo na rodada</p>
      ) : (
        <div className="space-y-2">
          {sorted.map((m) => (
            <div
              key={m.id}
              className={`rounded-lg p-3 border ${
                m.status === "live"
                  ? "bg-red-500/[0.08] border-red-500/20"
                  : "bg-white/[0.02] border-white/[0.06]"
              }`}
            >
              {m.status === "live" && (
                <div className="text-[10px] font-semibold text-red-500 mb-1">
                  ● AO VIVO
                </div>
              )}
              {m.status === "scheduled" && m.started_at && (
                <div className="text-[10px] text-gray-500 mb-1">
                  {formatDate(m.started_at)}, {formatTime(m.started_at)}
                </div>
              )}
              {m.status === "finished" && (
                <div className="text-[10px] text-green-500 mb-1">Encerrado</div>
              )}
              <div className="flex justify-between items-center text-sm">
                <span>{m.home_team_name}</span>
                {m.status !== "scheduled" ? (
                  <span className="font-bold">{m.home_score} × {m.away_score}</span>
                ) : (
                  <span className="text-gray-500">×</span>
                )}
                <span className="text-right">{m.away_team_name}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
