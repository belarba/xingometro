import { useState, useEffect } from "react";
import Navbar from "./components/Navbar";
import RoundFilter from "./components/RoundFilter";
import RageRanking from "./components/RageRanking";
import RageTimeline from "./components/RageTimeline";
import TopCoach from "./components/TopCoach";
import WordCloud from "./components/WordCloud";
import LiveFeed from "./components/LiveFeed";
import { useSSE } from "./hooks/useSSE";
import { useRankings } from "./hooks/useRankings";
import { fetchCoachRankings, fetchLiveStatus } from "./services/api";
import type { CoachRanking, LiveStatus } from "./types";

export default function App() {
  const [selectedRound, setSelectedRound] = useState<number | null>(null);
  const [coachRankings, setCoachRankings] = useState<CoachRanking[]>([]);
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null);

  const { posts, latestRanking, isConnected } = useSSE();
  const { rankings } = useRankings(selectedRound, latestRanking);

  // Fetch coach rankings
  useEffect(() => {
    fetchCoachRankings(selectedRound ?? undefined)
      .then(setCoachRankings)
      .catch(() => setCoachRankings([]));
  }, [selectedRound]);

  // Fetch live status periodically
  useEffect(() => {
    const load = () => {
      fetchLiveStatus()
        .then(setLiveStatus)
        .catch(() => {});
    };
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  // Merge SSE connection state into liveStatus
  const mergedLiveStatus: LiveStatus | null = liveStatus
    ? { ...liveStatus, connected: isConnected }
    : isConnected
      ? { connected: true, posts_per_minute: 0, active_matches: 0 }
      : null;

  return (
    <div className="min-h-screen">
      <Navbar round={selectedRound} liveStatus={mergedLiveStatus} />

      <div className="px-6 py-4">
        <div className="mb-4">
          <RoundFilter
            selectedRound={selectedRound}
            onRoundChange={setSelectedRound}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
          {/* Left column */}
          <div className="space-y-4">
            <RageRanking rankings={rankings} />
            <RageTimeline matchId={null} round={selectedRound} />
          </div>

          {/* Right column */}
          <div className="space-y-4">
            <TopCoach coachRankings={coachRankings} />
            <WordCloud round={selectedRound} />
            <LiveFeed posts={posts} />
          </div>
        </div>
      </div>
    </div>
  );
}
