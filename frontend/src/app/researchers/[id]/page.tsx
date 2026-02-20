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
import { ExternalLink, ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ProfileDetail } from "@/types/phoenix";

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
      <CardContent>
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
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No snapshots yet</p>
        )}
        {latestSnapshot &&
          (latestSnapshot.critical_count ||
            latestSnapshot.high_count ||
            latestSnapshot.medium_count ||
            latestSnapshot.low_count) && (
            <div className="mt-3 flex gap-2">
              {latestSnapshot.critical_count != null &&
                latestSnapshot.critical_count > 0 && (
                  <Badge className="bg-red-500/20 text-red-400">
                    C: {latestSnapshot.critical_count}
                  </Badge>
                )}
              {latestSnapshot.high_count != null &&
                latestSnapshot.high_count > 0 && (
                  <Badge className="bg-orange-500/20 text-orange-400">
                    H: {latestSnapshot.high_count}
                  </Badge>
                )}
              {latestSnapshot.medium_count != null &&
                latestSnapshot.medium_count > 0 && (
                  <Badge className="bg-yellow-500/20 text-yellow-400">
                    M: {latestSnapshot.medium_count}
                  </Badge>
                )}
              {latestSnapshot.low_count != null &&
                latestSnapshot.low_count > 0 && (
                  <Badge className="bg-blue-500/20 text-blue-400">
                    L: {latestSnapshot.low_count}
                  </Badge>
                )}
            </div>
          )}
        {profile.social_links.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {profile.social_links.map((sl) => (
              <Badge
                key={`${sl.platform}-${sl.handle}`}
                variant="outline"
                className="text-xs"
              >
                {sl.platform}: {sl.handle}
              </Badge>
            ))}
          </div>
        )}
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

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/researchers"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" /> Back to researchers
        </Link>
        <h1 className="text-2xl font-bold">{data.canonical_name}</h1>
        <p className="text-muted-foreground">
          Composite Score: {data.composite_score.toFixed(1)} &middot;{" "}
          {data.profiles.length} platform{data.profiles.length !== 1 ? "s" : ""}
        </p>
      </div>

      <Separator />

      <div className="grid gap-4 md:grid-cols-2">
        {data.profiles.map((profile) => (
          <ProfileCard key={profile.id} profile={profile} />
        ))}
      </div>

      <SnapshotChart profiles={data.profiles} />
    </div>
  );
}
