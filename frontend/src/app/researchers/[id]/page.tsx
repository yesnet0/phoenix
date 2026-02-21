"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getResearcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  ExternalLink,
  ArrowLeft,
  MapPin,
  Calendar,
  Shield,
  Tag,
  Link2,
  GitBranch,
  TrendingUp,
  Bug,
  Trophy,
} from "lucide-react";
import Link from "next/link";
import type { ProfileDetail, IdentityLinkDetail } from "@/types/phoenix";

const METRIC_OPTIONS = [
  { key: "overall_score", label: "Score" },
  { key: "global_rank", label: "Rank" },
  { key: "total_earnings", label: "Earnings" },
  { key: "finding_count", label: "Findings" },
] as const;

function ProfileCard({ profile }: { profile: ProfileDetail }) {
  const latestSnapshot = profile.snapshots
    .sort((a, b) => b.captured_at.localeCompare(a.captured_at))[0];

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">
              {profile.display_name || profile.username}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              @{profile.username} on {profile.platform_name}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{profile.platform_name}</Badge>
            {profile.profile_url && (
              <a
                href={profile.profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Bio */}
        {profile.bio && (
          <p className="text-sm text-muted-foreground line-clamp-3">{profile.bio}</p>
        )}

        {/* Location & dates */}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          {profile.location && (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" /> {profile.location}
            </span>
          )}
          {profile.join_date && (
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" /> Joined {profile.join_date.split("T")[0]}
            </span>
          )}
          {profile.last_scraped && (
            <span className="flex items-center gap-1">
              Scraped {profile.last_scraped.split("T")[0]}
            </span>
          )}
        </div>

        {/* Core stats */}
        {latestSnapshot ? (
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {latestSnapshot.global_rank != null && (
              <div>
                <p className="text-muted-foreground">Rank</p>
                <p className="font-mono font-medium">#{latestSnapshot.global_rank}</p>
              </div>
            )}
            {latestSnapshot.overall_score != null && (
              <div>
                <p className="text-muted-foreground">Score</p>
                <p className="font-mono font-medium">
                  {latestSnapshot.overall_score.toFixed(1)}
                </p>
              </div>
            )}
            {latestSnapshot.total_earnings != null && (
              <div>
                <p className="text-muted-foreground">Earnings</p>
                <p className="font-mono font-medium">
                  ${latestSnapshot.total_earnings.toLocaleString()}
                </p>
              </div>
            )}
            {latestSnapshot.finding_count != null && (
              <div>
                <p className="text-muted-foreground">Findings</p>
                <p className="font-mono font-medium">{latestSnapshot.finding_count}</p>
              </div>
            )}
            {latestSnapshot.signal_percentile != null && (
              <div>
                <p className="text-muted-foreground">Signal</p>
                <p className="font-mono font-medium">{latestSnapshot.signal_percentile.toFixed(0)}%</p>
              </div>
            )}
            {latestSnapshot.impact_percentile != null && (
              <div>
                <p className="text-muted-foreground">Impact</p>
                <p className="font-mono font-medium">{latestSnapshot.impact_percentile.toFixed(0)}%</p>
              </div>
            )}
            {latestSnapshot.acceptance_rate != null && (
              <div>
                <p className="text-muted-foreground">Acceptance</p>
                <p className="font-mono font-medium">{latestSnapshot.acceptance_rate.toFixed(0)}%</p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No snapshots yet</p>
        )}

        {/* Severity badges */}
        {latestSnapshot &&
          (latestSnapshot.critical_count ||
            latestSnapshot.high_count ||
            latestSnapshot.medium_count ||
            latestSnapshot.low_count) && (
            <div className="flex gap-2">
              {latestSnapshot.critical_count != null &&
                latestSnapshot.critical_count > 0 && (
                  <Badge className="bg-red-500/20 text-red-400">
                    Critical: {latestSnapshot.critical_count}
                  </Badge>
                )}
              {latestSnapshot.high_count != null &&
                latestSnapshot.high_count > 0 && (
                  <Badge className="bg-orange-500/20 text-orange-400">
                    High: {latestSnapshot.high_count}
                  </Badge>
                )}
              {latestSnapshot.medium_count != null &&
                latestSnapshot.medium_count > 0 && (
                  <Badge className="bg-yellow-500/20 text-yellow-400">
                    Medium: {latestSnapshot.medium_count}
                  </Badge>
                )}
              {latestSnapshot.low_count != null &&
                latestSnapshot.low_count > 0 && (
                  <Badge className="bg-blue-500/20 text-blue-400">
                    Low: {latestSnapshot.low_count}
                  </Badge>
                )}
            </div>
          )}

        {/* Badges */}
        {profile.badges && profile.badges.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {profile.badges.map((badge) => (
              <Badge key={badge} variant="outline" className="text-xs">
                <Shield className="mr-1 h-3 w-3" /> {badge}
              </Badge>
            ))}
          </div>
        )}

        {/* Skill tags */}
        {profile.skill_tags && profile.skill_tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {profile.skill_tags.map((tag) => (
              <Badge key={tag} className="bg-primary/10 text-primary text-xs">
                <Tag className="mr-1 h-3 w-3" /> {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Social links */}
        {profile.social_links.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {profile.social_links.map((sl) => (
              <Badge
                key={`${sl.platform}-${sl.handle}`}
                variant="outline"
                className="text-xs"
              >
                <Link2 className="mr-1 h-3 w-3" />
                {sl.platform}: {sl.handle}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function IdentityChain({ links }: { links: IdentityLinkDetail[] }) {
  if (!links || links.length === 0) return null;

  // Group by key_type + key_value
  const grouped = new Map<string, IdentityLinkDetail[]>();
  for (const link of links) {
    const key = `${link.key_type}:${link.key_value}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(link);
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <GitBranch className="h-4 w-4" /> Identity Resolution
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {[...grouped.entries()].map(([key, profileLinks]) => (
            <div key={key} className="rounded-md border p-3">
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="secondary" className="text-xs font-mono">
                  {key}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  matched {profileLinks.length} profile{profileLinks.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {profileLinks.map((pl) => (
                  <Badge key={pl.link_id + pl.profile_id} variant="outline" className="text-xs">
                    {pl.platform_name}: @{pl.username}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function SnapshotChart({ profiles }: { profiles: ProfileDetail[] }) {
  const [metric, setMetric] = useState<string>("overall_score");

  const allData: Record<string, Record<string, number | string>> = {};
  for (const profile of profiles) {
    for (const snap of profile.snapshots) {
      const date = snap.captured_at.split("T")[0];
      if (!allData[date]) allData[date] = { date };
      const val = snap[metric as keyof typeof snap];
      if (val != null && typeof val === "number") {
        allData[date][`${profile.platform_name}:${profile.username}`] = val;
      }
    }
  }
  const chartData = Object.values(allData).sort((a, b) =>
    (a.date as string).localeCompare(b.date as string)
  );

  const seriesKeys = [
    ...new Set(profiles.map((p) => `${p.platform_name}:${p.username}`)),
  ];

  const colors = [
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#ef4444",
    "#06b6d4",
  ];

  if (chartData.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Metrics Over Time</CardTitle>
          <div className="flex gap-1">
            {METRIC_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setMetric(opt.key)}
                className={`rounded px-2 py-1 text-xs transition-colors ${
                  metric === opt.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            {seriesKeys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[i % colors.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export default function ResearcherDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading } = useQuery({
    queryKey: ["researcher", id],
    queryFn: () => getResearcher(id),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (!data) {
    return <p className="text-muted-foreground">Researcher not found.</p>;
  }

  // Aggregate stats across profiles
  const totalEarnings = data.profiles.reduce((sum, p) => {
    const snap = p.snapshots.sort((a, b) => b.captured_at.localeCompare(a.captured_at))[0];
    return sum + (snap?.total_earnings || 0);
  }, 0);
  const totalFindings = data.profiles.reduce((sum, p) => {
    const snap = p.snapshots.sort((a, b) => b.captured_at.localeCompare(a.captured_at))[0];
    return sum + (snap?.finding_count || 0);
  }, 0);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/researchers"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" /> Back to researchers
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{data.canonical_name}</h1>
          {data.composite_score > 0 && (
            <Badge className="text-sm font-mono">
              <TrendingUp className="mr-1 h-3 w-3" />
              {data.composite_score >= 1000
                ? `${(data.composite_score / 1000).toFixed(1)}K`
                : data.composite_score.toFixed(0)}
            </Badge>
          )}
        </div>
        <div className="mt-1 flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>{data.profiles.length} platform{data.profiles.length !== 1 ? "s" : ""}</span>
          {totalEarnings > 0 && (
            <span className="font-mono">${totalEarnings.toLocaleString()} total earnings</span>
          )}
          {totalFindings > 0 && (
            <span className="flex items-center gap-1">
              <Bug className="h-3 w-3" /> {totalFindings.toLocaleString()} findings
            </span>
          )}
          <span>Tracked since {data.created_at?.split?.("T")?.[0] || "unknown"}</span>
        </div>
      </div>

      <Separator />

      {/* Identity resolution chain */}
      <IdentityChain links={data.identity_links} />

      {/* Profile cards */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Platform Profiles</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {data.profiles.map((profile) => (
            <ProfileCard key={profile.id} profile={profile} />
          ))}
        </div>
      </div>

      <SnapshotChart profiles={data.profiles} />
    </div>
  );
}
