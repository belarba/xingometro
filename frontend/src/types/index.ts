export interface Team {
  id: number;
  name: string;
  short_name: string;
}

export interface Coach {
  id: number;
  name: string;
  team_id: number;
}

export interface RankingEntry {
  team_id: number;
  team_name: string;
  short_name: string;
  avg_rage_score: number;
  post_count: number;
}

export interface CoachRanking {
  coach_id: number;
  coach_name: string;
  team_name: string;
  avg_rage_score: number;
  post_count: number;
  top_words: Record<string, number>;
}

export interface TimelinePoint {
  minute: number;
  avg_rage_score: number;
  post_count: number;
}

export interface MatchEvent {
  minute: number;
  type: string;
  team_id: number;
  description: string;
}

export interface Match {
  id: number;
  round: number;
  home_team_id: number;
  away_team_id: number;
  home_team_name: string;
  away_team_name: string;
  home_score: number;
  away_score: number;
  status: string;
  events: MatchEvent[];
  started_at: string;
}

export interface LivePost {
  id: number;
  author_handle: string;
  text: string;
  team_id: number;
  team_name: string;
  coach_id: number | null;
  rage_score: number;
  swear_words: string[];
  created_at: string;
}

export interface WordEntry {
  word: string;
  count: number;
  level: number;
}

export interface LiveStatus {
  connected: boolean;
  posts_per_minute: number;
  active_matches: number;
}
