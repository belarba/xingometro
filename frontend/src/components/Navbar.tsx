import type { LiveStatus } from "../types";

interface NavbarProps {
  round: number | null;
  liveStatus: LiveStatus | null;
}

export default function Navbar({ round, liveStatus }: NavbarProps) {
  const isLive =
    liveStatus?.connected && (liveStatus?.active_matches ?? 0) > 0;

  return (
    <nav className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08]">
      <div className="flex items-center gap-3">
        <span className="text-2xl">🤬</span>
        <h1 className="text-xl font-bold tracking-tight">Xingometro</h1>
        <span className="text-sm text-gray-500 ml-1">Brasileirao 2026</span>
      </div>

      <div className="flex items-center gap-6">
        {round !== null && (
          <span className="text-sm text-gray-400">
            Rodada {round}
          </span>
        )}

        {liveStatus && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span>{liveStatus.active_matches} jogos ativos</span>
            <span>{liveStatus.posts_per_minute} posts/min</span>
          </div>
        )}

        {isLive && (
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
            </span>
            <span className="text-sm font-semibold text-red-500">AO VIVO</span>
          </div>
        )}
      </div>
    </nav>
  );
}
