import type { CoachRanking } from "../types";

interface TopCoachProps {
  coachRankings: CoachRanking[];
}

function getRageColor(score: number): string {
  if (score >= 7) return "text-red-500";
  if (score >= 4) return "text-orange-500";
  if (score >= 2) return "text-yellow-500";
  return "text-gray-500";
}

export default function TopCoach({ coachRankings }: TopCoachProps) {
  if (coachRankings.length === 0) {
    return (
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3">Tecnico Mais Xingado</h2>
        <p className="text-gray-500 text-sm">Nenhum dado disponivel</p>
      </div>
    );
  }

  const top = coachRankings[0];
  const topWords = Object.entries(top.top_words)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">Tecnico Mais Xingado</h2>

      <div className="text-center">
        <span className="text-4xl mb-2 block">😤</span>
        <h3 className="text-xl font-bold">{top.coach_name}</h3>
        <p className="text-sm text-gray-400 mt-1">{top.team_name}</p>

        <div className="mt-4">
          <span className={`text-4xl font-black ${getRageColor(top.avg_rage_score)}`}>
            {top.avg_rage_score.toFixed(1)}
          </span>
          <p className="text-xs text-gray-500 mt-1">rage score medio</p>
        </div>

        <p className="text-xs text-gray-500 mt-2">{top.post_count} posts</p>

        {topWords.length > 0 && (
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {topWords.map(([word, count]) => (
              <span
                key={word}
                className="bg-red-500/10 text-red-400 text-xs px-2 py-1 rounded-full"
              >
                {word} ({count})
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
