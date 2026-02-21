import type {
  Analytics,
  GraphData,
  HealthStatus,
  JobStatus,
  ProfileListItem,
  ResearcherDetail,
  ResearcherSummary,
  ScrapeHealth,
  SearchResult,
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
