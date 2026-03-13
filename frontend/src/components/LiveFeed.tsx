import { useEffect, useRef } from "react";
import type { LivePost } from "../types";

interface LiveFeedProps {
  posts: LivePost[];
}

function getRageBadgeStyle(score: number): string {
  if (score >= 7) return "bg-red-500/20 text-red-400";
  if (score >= 4) return "bg-orange-500/20 text-orange-400";
  if (score >= 2) return "bg-yellow-500/20 text-yellow-400";
  return "bg-gray-500/20 text-gray-400";
}

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function LiveFeed({ posts }: LiveFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to top when new posts arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [posts.length]);

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Feed ao Vivo</h2>
        <span className="text-xs text-gray-500">{posts.length} posts</span>
      </div>

      <div
        ref={containerRef}
        className="space-y-2 max-h-[500px] overflow-y-auto pr-1"
      >
        {posts.length === 0 ? (
          <p className="text-gray-500 text-sm py-8 text-center">
            Aguardando posts...
          </p>
        ) : (
          posts.map((post) => (
            <div
              key={post.id}
              className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-3"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-300">
                    @{post.author_handle}
                  </span>
                  <span className="text-xs text-gray-600">
                    {post.team_name}
                  </span>
                </div>

                <span
                  className={`text-xs font-bold px-2 py-0.5 rounded-full ${getRageBadgeStyle(post.rage_score)}`}
                >
                  {post.rage_score.toFixed(1)}
                </span>
              </div>

              <p className="text-sm text-gray-300 leading-relaxed">
                {post.text}
              </p>

              <div className="flex items-center justify-between mt-2">
                {post.swear_words.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {post.swear_words.map((w, i) => (
                      <span
                        key={i}
                        className="text-[10px] bg-red-500/10 text-red-400/60 px-1.5 py-0.5 rounded"
                      >
                        {w}
                      </span>
                    ))}
                  </div>
                )}
                <span className="text-[10px] text-gray-600 ml-auto">
                  {formatTime(post.created_at)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
