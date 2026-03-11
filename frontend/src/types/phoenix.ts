// TypeScript types matching Phoenix backend models

export interface ResearcherSummary {
  id: string;
  canonical_name: string;
  composite_score: number;
  profiles: { platform: string; username: string }[];
  platform_count: number;
  total_earnings: number;
  total_findings: number;
  top_score: number | null;
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
  location: string;
  badges: string[];
  skill_tags: string[];
  join_date: string | null;
  last_active: string | null;
  last_scraped: string | null;
  snapshots: ProfileSnapshot[];
  social_links: SocialLink[];
}

export interface IdentityLinkDetail {
  link_id: string;
  key_type: string;
  key_value: string;
  confidence: number;
  resolved_at: string;
  profile_id: string;
  platform_name: string;
  username: string;
}

export interface ResearcherDetail {
  id: string;
  canonical_name: string;
  composite_score: number;
  created_at: string;
  profiles: ProfileDetail[];
  identity_links: IdentityLinkDetail[];
}

export interface ProfileListItem {
  profile_id: string;
  platform_name: string;
  username: string;
  display_name: string;
  profile_url: string;
  bio: string;
  location: string;
  badges: string[];
  score: number | null;
  rank: number | null;
  earnings: number | null;
  findings: number | null;
  critical: number | null;
  high: number | null;
  medium: number | null;
  low: number | null;
  researcher_id: string | null;
  researcher_name: string | null;
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
  total_findings: number;
  top_score: number | null;
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

// M4 Insights types

export interface SkillDistribution {
  skill: string;
  profile_count: number;
  researcher_count: number;
}

export interface SkillResearcher {
  id: string;
  canonical_name: string;
  composite_score: number;
  profiles: { platform: string; username: string; source: string }[];
  profile_count: number;
}

export interface RisingStar {
  id: string;
  name: string;
  composite_score: number;
  score_delta: number;
  finding_delta: number;
}

export interface HeatmapEntry {
  month: string;
  profile_count: number;
}

export interface FindingVelocity {
  id: string;
  name: string;
  total_finding_delta: number;
  days_tracked: number;
  findings_per_month: number;
}

export interface PlatformComparison {
  platform: string;
  profile_count: number;
  avg_score: number;
  avg_findings: number;
  avg_earnings: number;
}

export interface PlatformOverlap {
  platform_a: string;
  platform_b: string;
  shared_researchers: number;
}

export interface PlatformAffinity {
  platform_a: string;
  platform_b: string;
  shared: number;
  affinity_score: number;
}

export interface SimilarResearcher {
  id: string;
  name: string;
  composite_score: number;
  shared_skills: number;
  similarity: number;
}
