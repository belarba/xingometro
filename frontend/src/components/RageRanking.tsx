import { useState } from "react";
import type { RankingEntry } from "../types";
import TeamDetailModal from "./TeamDetailModal";

interface RageRankingProps {
  rankings: RankingEntry[];
}

function getRageColor(score: number): string {
  if (score >= 7) return "bg-red-500";
  if (score >= 4) return "bg-orange-500";
  if (score >= 2) return "bg-yellow-500";
  return "bg-gray-500";
}

function getRageTextColor(score: number): string {
  if (score >= 7) return "text-red-500";
  if (score >= 4) return "text-orange-500";
  if (score >= 2) return "text-yellow-500";
  return "text-gray-500";
}

export default function RageRanking({ rankings }: RageRankingProps) {
  const maxScore = Math.max(...rankings.map((r) => r.avg_rage_score), 1);
  const [selectedTeam, setSelectedTeam] = useState<RankingEntry | null>(null);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">Ranking de Raiva</h2>

      {rankings.length === 0 ? (
        <p className="text-gray-500 text-sm">Nenhum dado disponivel</p>
      ) : (
        <div className="space-y-3">
          {rankings.map((entry, idx) => (
            <div
              key={entry.team_id}
              className="flex items-center gap-3 cursor-pointer rounded-lg px-1 py-0.5 -mx-1 hover:bg-white/[0.05] transition-colors"
              onClick={() => setSelectedTeam(entry)}
            >
              <span className="text-gray-500 text-sm w-6 text-right font-mono">
                {idx + 1}
              </span>

              <span className="text-sm font-medium w-28 truncate">
                {entry.short_name || entry.team_name}
              </span>

              <div className="flex-1 h-6 bg-white/[0.05] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${getRageColor(entry.avg_rage_score)}`}
                  style={{
                    width: `${(entry.avg_rage_score / maxScore) * 100}%`,
                  }}
                />
              </div>

              <span
                className={`text-sm font-bold w-10 text-right ${getRageTextColor(entry.avg_rage_score)}`}
              >
                {entry.avg_rage_score.toFixed(1)}
              </span>

              <span className="text-xs text-gray-500 w-16 text-right">
                {entry.post_count} posts
              </span>
            </div>
          ))}
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
