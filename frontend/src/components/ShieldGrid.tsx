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
