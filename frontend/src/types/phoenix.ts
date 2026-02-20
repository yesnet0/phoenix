// TypeScript types matching Phoenix backend models

export interface ResearcherSummary {
  id: string;
  canonical_name: string;
  composite_score: number;
  profiles: { platform: string; username: string }[];
}

export interface SocialLink {
  platform: string;
  handle: string;
  raw_value: string;
}

export interface ProfileSnapshot {
  id: string;
  captured_at: string;
  overall_score: number | null;
  global_rank: number | null;
  total_earnings: number | null;
  finding_count: number | null;
  critical_count: number | null;
  high_count: number | null;
  medium_count: number | null;
  low_count: number | null;
  signal_percentile: number | null;
  impact_percentile: number | null;
  acceptance_rate: number | null;
  raw_data: string;
}

export interface ProfileDetail {
  id: string;
  platform_name: string;
  username: string;
  display_name: string;
  bio: string;
  profile_url: string;
  snapshots: ProfileSnapshot[];
  social_links: SocialLink[];
}

export interface ResearcherDetail {
  id: string;
  canonical_name: string;
  composite_score: number;
  created_at: string;
  profiles: ProfileDetail[];
}

export interface SearchResult {
  profile_id: string;
  platform_name: string;
  username: string;
  display_name: string;
  profile_url: string;
  researcher_id: string | null;
  researcher_name: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  type: "researcher" | "platform" | "profile";
  size: number;
  score?: number;
  platform?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: "on_platform" | "belongs_to";
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AnalyticsCounts {
  researchers: number;
  profiles: number;
  platforms: number;
  snapshots: number;
  social_links: number;
}

export interface TopResearcher {
  id: string;
  name: string;
  score: number;
  platform_count: number;
}

export interface TopEarner {
  id: string;
  name: string;
  total_earnings: number;
}

export interface PlatformCoverage {
  platform: string;
  profile_count: number;
}

export interface CrossPlatform {
  num_platforms: number;
  researcher_count: number;
}

export interface Analytics {
  counts: AnalyticsCounts;
  top_by_score: TopResearcher[];
  top_by_earnings: TopEarner[];
  platform_coverage: PlatformCoverage[];
  cross_platform_distribution: CrossPlatform[];
}

export interface ScrapeHealth {
  total: number;
  ok: number;
  failing: number;
  platforms: Record<
    string,
    {
      status: string;
      entries?: number;
      error?: string;
      checked_at: string;
    }
  >;
}

export interface TriggerResponse {
  job_id: string;
  status: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  result?: {
    job_id: string;
    profiles_scraped: number;
    profiles_failed: number;
    identities_resolved: number;
    duration_seconds: number;
    errors: string[];
  };
}

export interface HealthStatus {
  status: string;
  neo4j: string;
}
