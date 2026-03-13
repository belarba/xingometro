import { useState, useEffect, useRef, useCallback } from "react";
import type { LivePost, RankingEntry } from "../types";

const MAX_POSTS = 50;
const RECONNECT_DELAY = 3000;

interface UseSSEReturn {
  posts: LivePost[];
  latestRanking: RankingEntry[] | null;
  isConnected: boolean;
}

export function useSSE(): UseSSEReturn {
  const [posts, setPosts] = useState<LivePost[]>([]);
  const [latestRanking, setLatestRanking] = useState<RankingEntry[] | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource("/api/live/feed");
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
    };

    es.addEventListener("new_post", (event) => {
      try {
        const post: LivePost = JSON.parse(event.data);
        setPosts((prev) => [post, ...prev].slice(0, MAX_POSTS));
      } catch {
        // ignore parse errors
      }
    });

    es.addEventListener("ranking_update", (event) => {
      try {
        const ranking: RankingEntry[] = JSON.parse(event.data);
        setLatestRanking(ranking);
      } catch {
        // ignore parse errors
      }
    });

    es.onerror = () => {
      setIsConnected(false);
      es.close();
      eventSourceRef.current = null;

      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, RECONNECT_DELAY);
    };
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connect]);

  return { posts, latestRanking, isConnected };
}
