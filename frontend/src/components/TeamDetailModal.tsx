import { useEffect, useState } from "react";
import type { TeamStats } from "../types";
import { fetchTeamStats } from "../services/api";

interface TeamDetailModalProps {
  teamId: number;
  teamName: string;
  shortName: string;
  onClose: () => void;
}

function getRageColor(score: number): string {
  if (score >= 7) return "text-red-500";
  if (score >= 4) return "text-orange-500";
  if (score >= 2) return "text-yellow-500";
  return "text-gray-400";
}

function getBarColor(level: number): string {
  if (level >= 4) return "bg-red-500";
  if (level >= 3) return "bg-orange-500";
  return "bg-yellow-500";
}

export default function TeamDetailModal({
  teamId,
  teamName,
  shortName,
  onClose,
}: TeamDetailModalProps) {
  const [stats, setStats] = useState<TeamStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchTeamStats(teamId)
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, [teamId]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const wordEntries = stats
    ? Object.entries(stats.top_swear_words).slice(0, 8)
    : [];
  const maxWordCount = wordEntries.length
    ? Math.max(...wordEntries.map(([, c]) => c))
    : 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-[#1a1a2e] border border-white/10 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <h3 className="text-lg font-bold">{teamName}</h3>
            <span className="text-xs text-gray-400">{shortName}</span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none px-2 py-1 rounded hover:bg-white/10 transition-colors"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : !stats ? (
            <p className="text-gray-500 text-sm text-center py-8">
              Erro ao carregar dados
            </p>
          ) : (
            <div className="space-y-5">
              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-white/[0.05] rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold">{stats.total_posts}</div>
                  <div className="text-xs text-gray-400 mt-1">Posts</div>
                </div>
                <div className="bg-white/[0.05] rounded-lg p-3 text-center">
                  <div
                    className={`text-2xl font-bold ${getRageColor(stats.avg_rage_score)}`}
                  >
                    {stats.avg_rage_score.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">Raiva Media</div>
                </div>
                <div className="bg-white/[0.05] rounded-lg p-3 text-center">
                  <div
                    className={`text-2xl font-bold ${getRageColor(stats.max_rage_score)}`}
                  >
                    {stats.max_rage_score.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">Raiva Max</div>
                </div>
              </div>

              {/* Rage meter */}
              <div>
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>Nivel de raiva</span>
                  <span>{stats.avg_rage_score.toFixed(1)} / 10</span>
                </div>
                <div className="h-3 bg-white/[0.05] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${(stats.avg_rage_score / 10) * 100}%`,
                      background: `linear-gradient(90deg, #eab308 0%, #f97316 50%, #ef4444 100%)`,
                    }}
                  />
                </div>
              </div>

              {/* Top swear words */}
              {wordEntries.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-300 mb-2">
                    Top Palavroes
                  </h4>
                  <div className="space-y-1.5">
                    {wordEntries.map(([word, count], i) => (
                      <div key={word} className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 w-4 text-right">
                          {i + 1}
                        </span>
                        <span className="text-sm w-28 truncate">{word}</span>
                        <div className="flex-1 h-4 bg-white/[0.05] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${getBarColor(count > maxWordCount * 0.6 ? 4 : count > maxWordCount * 0.3 ? 3 : 2)}`}
                            style={{
                              width: `${(count / maxWordCount) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-400 w-8 text-right">
                          {count}x
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
