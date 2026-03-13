import { useState, useEffect } from "react";
import type { WordEntry } from "../types";
import { fetchWords } from "../services/api";

interface WordCloudProps {
  round: number | null;
  teamId?: number;
}

function getLevelColor(level: number): string {
  switch (level) {
    case 1:
      return "text-green-400";
    case 2:
      return "text-yellow-400";
    case 3:
      return "text-red-400";
    case 4:
      return "text-purple-400";
    default:
      return "text-gray-400";
  }
}

function getFontSize(count: number, maxCount: number): number {
  const minSize = 12;
  const maxSize = 36;
  if (maxCount <= 1) return minSize;
  return minSize + ((count / maxCount) * (maxSize - minSize));
}

export default function WordCloud({ round, teamId }: WordCloudProps) {
  const [words, setWords] = useState<WordEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchWords(round ?? undefined, teamId)
      .then(setWords)
      .catch(() => setWords([]))
      .finally(() => setLoading(false));
  }, [round, teamId]);

  const maxCount = Math.max(...words.map((w) => w.count), 1);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">Palavras Mais Usadas</h2>

      {loading ? (
        <p className="text-gray-500 text-sm">Carregando...</p>
      ) : words.length === 0 ? (
        <p className="text-gray-500 text-sm">Nenhum dado disponivel</p>
      ) : (
        <div className="flex flex-wrap gap-2 justify-center py-2">
          {words.map((entry) => (
            <span
              key={entry.word}
              className={`inline-block cursor-default transition-opacity hover:opacity-80 ${getLevelColor(entry.level)}`}
              style={{
                fontSize: `${getFontSize(entry.count, maxCount)}px`,
                lineHeight: 1.2,
              }}
              title={`${entry.word}: ${entry.count}x (nivel ${entry.level})`}
            >
              {entry.word}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
