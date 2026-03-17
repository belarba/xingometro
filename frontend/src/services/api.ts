import type {
  RankingEntry,
  CoachRanking,
  TimelinePoint,
  Match,
  WordEntry,
  LiveStatus,
  TeamStats,
  StandingEntry,
  CorrelationEntry,
  PositionHistoryEntry,
} from "../types";

function buildParams(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null
  );
  if (entries.length === 0) return "";
  const search = new URLSearchParams();
  entries.forEach(([k, v]) => search.set(k, String(v)));
  return `?${search.toString()}`;
}

export async function fetchRankings(round?: number): Promise<RankingEntry[]> {
  const res = await fetch(`/api/rankings${buildParams({ round })}`);
  if (!res.ok) throw new Error("Failed to fetch rankings");
  return res.json();
}

export async function fetchCoachRankings(round?: number): Promise<CoachRanking[]> {
  const res = await fetch(`/api/rankings/coaches${buildParams({ round })}`);
  if (!res.ok) throw new Error("Failed to fetch coach rankings");
  return res.json();
}

export async function fetchTimeline(
  matchId: number
): Promise<{ points: TimelinePoint[]; events: { minute: number; type: string; team_id: number; description: string }[] }> {
  const res = await fetch(`/api/timeline/${matchId}`);
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}

export async function fetchMatches(
  round?: number,
  status?: string
): Promise<Match[]> {
  const res = await fetch(`/api/matches${buildParams({ round, status })}`);
  if (!res.ok) throw new Error("Failed to fetch matches");
  return res.json();
}

export async function fetchRounds(): Promise<number[]> {
  const res = await fetch("/api/rounds");
  if (!res.ok) throw new Error("Failed to fetch rounds");
  return res.json();
}

export async function fetchWords(
  round?: number,
  teamId?: number
): Promise<WordEntry[]> {
  const res = await fetch(
    `/api/words${buildParams({ round, team_id: teamId })}`
  );
  if (!res.ok) throw new Error("Failed to fetch words");
  return res.json();
}

export async function fetchTeamStats(teamId: number): Promise<TeamStats> {
  const res = await fetch(`/api/stats/${teamId}`);
  if (!res.ok) throw new Error("Failed to fetch team stats");
  return res.json();
}

export async function fetchLiveStatus(): Promise<LiveStatus> {
  const res = await fetch("/api/live/status");
  if (!res.ok) throw new Error("Failed to fetch live status");
  return res.json();
}

export async function fetchStandings(): Promise<StandingEntry[]> {
  const res = await fetch("/api/standings");
  if (!res.ok) throw new Error("Failed to fetch standings");
  return res.json();
}

export async function fetchCorrelation(round?: number): Promise<CorrelationEntry[]> {
  const res = await fetch(`/api/stats/correlation${buildParams({ round })}`);
  if (!res.ok) throw new Error("Failed to fetch correlation data");
  return res.json();
}

export async function fetchPositionHistory(teamId: number): Promise<PositionHistoryEntry[]> {
  const res = await fetch(`/api/stats/position-history/${teamId}`);
  if (!res.ok) throw new Error("Failed to fetch position history");
  return res.json();
}
