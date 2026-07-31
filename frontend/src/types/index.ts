export interface User {
  id: number;
  email: string;
  username: string;
  is_admin: boolean;
  language: string;
  country: string | null;
  plan: "free" | "pro";
}

export interface Source {
  id: number;
  name: string;
  url: string;
  type: "telegram" | "website" | "rss";
  language: string;
  country: string | null;
  topics: string[];
  enabled: boolean;       // per current user
  blacklisted: boolean;
}

export interface NewsItem {
  id: number;
  source: Source;
  title: string | null;
  body: string;
  summary: string | null;
  url: string | null;
  image_url: string | null;
  language: string;
  topics: Record<string, number>;     // { politics: 0.9, tech: 0.2 }
  importance_score: number;
  published_at: string | null;
  created_at: string;
  reaction: "like" | "dislike" | "blacklist" | null;
  likes_count: number;
  dislikes_count: number;
}

export interface TopicPreference {
  topic: string;
  weight: number;   // 0.0 – 1.0
}

export interface PreferencesResponse {
  preferences: TopicPreference[];
}

export interface PreferencesUpdate {
  preferences: TopicPreference[];
}

export interface FeedFilters {
  topics?: string[];
  languages?: string[];
  countries?: string[];
  source_ids?: number[];
}
