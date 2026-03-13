import { useState, useEffect, useCallback } from "react";
import type { RankingEntry } from "../types";
import { fetchRankings } from "../services/api";

const REFRESH_INTERVAL = 30000;

interface UseRankingsReturn {
  rankings: RankingEntry[];
  loading: boolean;
  error: string | null;
}

export function useRankings(
  round: number | null,
  sseRanking: RankingEntry[] | null
): UseRankingsReturn {
  const [rankings, setRankings] = useState<RankingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchRankings(round ?? undefined);
      setRankings(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [round]);

  // Initial load + polling
  useEffect(() => {
    setLoading(true);
    load();

    const timer = setInterval(load, REFRESH_INTERVAL);
    return () => clearInterval(timer);
  }, [load]);

  // Real-time update from SSE
  useEffect(() => {
    if (sseRanking && sseRanking.length > 0) {
      setRankings(sseRanking);
    }
  }, [sseRanking]);

  return { rankings, loading, error };
}
