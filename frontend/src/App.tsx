import { useState, useEffect } from "react";
import Navbar from "./components/Navbar";
import RoundFilter from "./components/RoundFilter";
import RageRanking from "./components/RageRanking";
import RageTimeline from "./components/RageTimeline";
import TopCoach from "./components/TopCoach";
import WordCloud from "./components/WordCloud";
import LiveFeed from "./components/LiveFeed";
import TabNav from "./components/TabNav";
import MatchStrip from "./components/MatchStrip";
import StandingsTable from "./components/StandingsTable";
import MatchList from "./components/MatchList";
import ShieldGrid from "./components/ShieldGrid";
import CorrelationScatter from "./components/CorrelationScatter";
import PositionRoller from "./components/PositionRoller";
import { useSSE } from "./hooks/useSSE";
import { useRankings } from "./hooks/useRankings";
import { fetchCoachRankings, fetchLiveStatus, fetchMatches } from "./services/api";
import type { CoachRanking, LiveStatus, Match } from "./types";

export default function App() {
  const [selectedRound, setSelectedRound] = useState<number | null>(null);
  const [coachRankings, setCoachRankings] = useState<CoachRanking[]>([]);
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [activeTab, setActiveTab] = useState<"xingometro" | "classificacao">("xingometro");

  const { posts, latestRanking, isConnected } = useSSE();
  const { rankings } = useRankings(selectedRound, latestRanking);

  // Fetch coach rankings
  useEffect(() => {
    fetchCoachRankings(selectedRound ?? undefined)
      .then(setCoachRankings)
      .catch(() => setCoachRankings([]));
  }, [selectedRound]);

  // Fetch matches for ShieldGrid
  useEffect(() => {
    fetchMatches(selectedRound ?? undefined)
      .then(setMatches)
      .catch(() => setMatches([]));
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
      <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="px-6 py-4">
        <div className="mb-4">
          <RoundFilter
            selectedRound={selectedRound}
            onRoundChange={setSelectedRound}
          />
        </div>

        {activeTab === "xingometro" ? (
          <>
            <div className="mb-4">
              <MatchStrip round={selectedRound} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
              <div className="space-y-4">
                <RageRanking rankings={rankings} />
                <RageTimeline matchId={null} round={selectedRound} />
              </div>
              <div className="space-y-4">
                <TopCoach coachRankings={coachRankings} />
                <WordCloud round={selectedRound} />
                <LiveFeed posts={posts} />
              </div>
            </div>
            {/* Insights section */}
            <div className="mt-8">
              <h2 className="text-xl font-bold mb-4 text-gray-300">Insights</h2>
              <div className="space-y-4">
                <ShieldGrid rankings={rankings} matches={matches} />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <CorrelationScatter round={selectedRound} />
                  <PositionRoller rankings={rankings} />
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
            <StandingsTable />
            <MatchList round={selectedRound} />
          </div>
        )}
      </div>
    </div>
  );
}
