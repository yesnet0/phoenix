import type {
  Analytics,
  FindingVelocity,
  GraphData,
  HeatmapEntry,
  HealthStatus,
  JobStatus,
  PlatformAffinity,
  PlatformComparison,
  PlatformOverlap,
  ProfileListItem,
  ResearcherDetail,
  ResearcherSummary,
  RisingStar,
  ScrapeHealth,
  SearchResult,
  SimilarResearcher,
  SkillDistribution,
  SkillResearcher,
  TriggerResponse,
} from "@/types/phoenix";

const BASE = "/api";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Health
export const getHealth = () => fetchJSON<HealthStatus>("/health");

// Researchers
export const getResearchers = (skip = 0, limit = 50, sort = "score") =>
  fetchJSON<{ researchers: ResearcherSummary[]; total: number; count: number }>(
    `/researchers/?skip=${skip}&limit=${limit}&sort=${sort}`
  );

export const getResearcher = (id: string) =>
  fetchJSON<ResearcherDetail>(`/researchers/${id}`);

export const searchProfiles = (username: string) =>
  fetchJSON<{ results: SearchResult[]; count: number }>(
    `/researchers/search/${encodeURIComponent(username)}`
  );

// Profiles
export const getProfiles = (
  skip = 0,
  limit = 50,
  platform?: string,
  sort = "earnings"
) => {
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
    sort,
  });
  if (platform) params.set("platform", platform);
  return fetchJSON<{ profiles: ProfileListItem[]; count: number; platforms: string[] }>(
    `/researchers/profiles?${params}`
  );
};

// Graph
export const getGraphData = () => fetchJSON<GraphData>("/graph");

// Analytics
export const getAnalytics = () => fetchJSON<Analytics>("/analytics");

// Scrape
export const getPlatforms = () =>
  fetchJSON<{ platforms: string[] }>("/scrape/platforms");

export const triggerScrape = (platform_name: string, max_profiles = 50) =>
  fetchJSON<TriggerResponse>("/scrape/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ platform_name, max_profiles }),
  });

export const getJobStatus = (jobId: string) =>
  fetchJSON<JobStatus>(`/scrape/status/${jobId}`);

export const checkHealth = () =>
  fetchJSON<ScrapeHealth>("/scrape/health", { method: "POST" });

// Enrichment & scoring
export const triggerEnrich = () =>
  fetchJSON<{ github_links_added: number; profiles_checked: number }>("/scrape/enrich", {
    method: "POST",
  });

export const recomputeScores = () =>
  fetchJSON<{ updated: number }>("/analytics/recompute-scores", {
    method: "POST",
  });

// M4 Insights
export const getSkillDistribution = () =>
  fetchJSON<{ distribution: SkillDistribution[] }>("/analytics/skills");

export const getResearchersBySkill = (skill: string, skip = 0, limit = 50) =>
  fetchJSON<{ skill: string; researchers: SkillResearcher[]; count: number }>(
    `/analytics/skills?skill=${encodeURIComponent(skill)}&skip=${skip}&limit=${limit}`
  );

export const getRisingStars = (limit = 10) =>
  fetchJSON<{ rising_stars: RisingStar[] }>(`/analytics/rising-stars?limit=${limit}`);

export const getHeatmap = () =>
  fetchJSON<{ heatmap: HeatmapEntry[] }>("/analytics/heatmap");

export const getFindingVelocity = (limit = 10) =>
  fetchJSON<{ velocity: FindingVelocity[] }>(`/analytics/finding-velocity?limit=${limit}`);

export const getPlatformComparison = () =>
  fetchJSON<{ platforms: PlatformComparison[] }>("/analytics/platform-comparison");

export const getCrossPlatform = () =>
  fetchJSON<{ overlap: PlatformOverlap[]; affinity: PlatformAffinity[] }>(
    "/analytics/cross-platform"
  );

export const getSimilarResearchers = (id: string, limit = 5) =>
  fetchJSON<{ similar: SimilarResearcher[]; count: number }>(
    `/researchers/${id}/similar?limit=${limit}`
  );
