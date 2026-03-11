"use client";

import { useQuery } from "@tanstack/react-query";
import { getAnalytics, getRisingStars, getPlatformComparison, getHeatmap, getCrossPlatform } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Users, Globe, Camera, Link2, Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";

function formatScore(score: number): string {
  if (score >= 1_000_000) return `${(score / 1_000_000).toFixed(1)}M`;
  if (score >= 1_000) return `${(score / 1_000).toFixed(1)}K`;
  return score.toFixed(0);
}

function StatCard({
  label,
  value,
  icon: Icon,
  href,
}: {
  label: string;
  value: number | undefined;
  icon: React.ElementType;
  href?: string;
}) {
  const content = (
    <Card className={href ? "hover:border-primary/50 transition-colors cursor-pointer" : ""}>
      <CardContent className="flex items-center gap-4 p-6">
        <div className="rounded-lg bg-primary/10 p-3">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <div className="text-2xl font-bold">
            {value !== undefined ? value.toLocaleString() : <Skeleton className="h-8 w-16" />}
          </div>
        </div>
      </CardContent>
    </Card>
  );
  if (href) return <Link href={href}>{content}</Link>;
  return content;
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["analytics"],
    queryFn: getAnalytics,
    refetchInterval: 30000,
  });

  const multiPlatformCount = data?.cross_platform_distribution
    .filter((c) => c.num_platforms > 1)
    .reduce((sum, c) => sum + c.researcher_count, 0) ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        {data && (
          <Badge variant="outline" className="text-xs">
            {multiPlatformCount} multi-platform identities resolved
          </Badge>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Researchers" value={data?.counts.researchers} icon={Users} href="/researchers" />
        <StatCard label="Profiles" value={data?.counts.profiles} icon={Globe} href="/profiles" />
        <StatCard label="Platforms" value={data?.counts.platforms} icon={Activity} href="/scrape" />
        <StatCard label="Snapshots" value={data?.counts.snapshots} icon={Camera} />
        <StatCard label="Social Links" value={data?.counts.social_links} icon={Link2} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Top Researchers</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : data?.top_by_score.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8">#</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="text-right">Platforms</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_by_score.map((r, i) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                      <TableCell>
                        <Link
                          href={`/researchers/${r.id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {r.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatScore(r.score)}
                      </TableCell>
                      <TableCell className="text-right">
                        {r.platform_count > 1 ? (
                          <Badge variant="secondary" className="text-xs">
                            {r.platform_count}
                          </Badge>
                        ) : (
                          r.platform_count
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No researchers yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Most Active (Findings)</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : data?.top_by_earnings.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8">#</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">Findings</TableHead>
                    <TableHead className="text-right">Top Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_by_earnings.map((r, i) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                      <TableCell>
                        <Link
                          href={`/researchers/${r.id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {r.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {r.total_findings.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground">
                        {r.top_score ? formatScore(r.top_score) : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No findings data yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Platform Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : data?.platform_coverage.filter((p) => p.profile_count > 0).length ? (
              <div className="max-h-[400px] overflow-y-auto">
                <ResponsiveContainer width="100%" height={Math.max(280, data.platform_coverage.filter((p) => p.profile_count > 0).length * 28)}>
                  <BarChart
                    data={data.platform_coverage.filter((p) => p.profile_count > 0)}
                    layout="vertical"
                    margin={{ left: 80 }}
                  >
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="platform" width={75} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="profile_count" fill="hsl(var(--chart-1))" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No profiles scraped yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Cross-Platform Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : data?.cross_platform_distribution.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.cross_platform_distribution}>
                  <XAxis dataKey="num_platforms" label={{ value: "Platforms", position: "insideBottom", offset: -5 }} />
                  <YAxis label={{ value: "Researchers", angle: -90, position: "insideLeft" }} />
                  <Tooltip />
                  <Bar
                    dataKey="researcher_count"
                    fill="hsl(var(--chart-2))"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">No identity resolution data yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      <M4InsightsSection />
    </div>
  );
}

function M4InsightsSection() {
  const { data: risingData, isLoading: risingLoading } = useQuery({
    queryKey: ["risingStars"],
    queryFn: () => getRisingStars(5),
  });

  const { data: platformData, isLoading: platformLoading } = useQuery({
    queryKey: ["platformComparison"],
    queryFn: getPlatformComparison,
  });

  const { data: heatmapData, isLoading: heatmapLoading } = useQuery({
    queryKey: ["heatmap"],
    queryFn: getHeatmap,
  });

  const { data: crossData, isLoading: crossLoading } = useQuery({
    queryKey: ["crossPlatform"],
    queryFn: getCrossPlatform,
  });

  const filteredHeatmap = heatmapData?.heatmap
    .filter((e) => e.month !== "1970-01")
    .sort((a, b) => a.month.localeCompare(b.month));

  const topAffinity = crossData?.affinity
    .sort((a, b) => b.affinity_score - a.affinity_score)
    .slice(0, 10);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Rising Stars */}
      <Card>
        <CardHeader>
          <CardTitle>Rising Stars</CardTitle>
        </CardHeader>
        <CardContent>
          {risingLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : risingData?.rising_stars.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Score Delta</TableHead>
                  <TableHead className="text-right">Finding Delta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {risingData.rising_stars.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Link
                        href={`/researchers/${r.id}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {r.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      +{formatScore(r.score_delta)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      +{r.finding_delta}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No rising star data yet</p>
          )}
        </CardContent>
      </Card>

      {/* Platform Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>Platform Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          {platformLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : platformData?.platforms.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Platform</TableHead>
                  <TableHead className="text-right">Profiles</TableHead>
                  <TableHead className="text-right">Avg Score</TableHead>
                  <TableHead className="text-right">Avg Findings</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {platformData.platforms.map((p) => (
                  <TableRow key={p.platform}>
                    <TableCell className="font-medium">{p.platform}</TableCell>
                    <TableCell className="text-right">{p.profile_count.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono">{formatScore(p.avg_score)}</TableCell>
                    <TableCell className="text-right font-mono">{p.avg_findings.toFixed(1)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No platform data yet</p>
          )}
        </CardContent>
      </Card>

      {/* Activity Heatmap */}
      <Card>
        <CardHeader>
          <CardTitle>Activity Heatmap</CardTitle>
        </CardHeader>
        <CardContent>
          {heatmapLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : filteredHeatmap?.length ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={filteredHeatmap}>
                <XAxis dataKey="month" tick={{ fontSize: 11 }} angle={-45} textAnchor="end" height={60} />
                <YAxis label={{ value: "Profiles", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Bar
                  dataKey="profile_count"
                  fill="hsl(var(--chart-3))"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground">No heatmap data yet</p>
          )}
        </CardContent>
      </Card>

      {/* Platform Affinity */}
      <Card>
        <CardHeader>
          <CardTitle>Platform Affinity</CardTitle>
        </CardHeader>
        <CardContent>
          {crossLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : topAffinity?.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Platform A</TableHead>
                  <TableHead>Platform B</TableHead>
                  <TableHead className="text-right">Shared</TableHead>
                  <TableHead className="text-right">Affinity Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topAffinity.map((a, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{a.platform_a}</TableCell>
                    <TableCell className="font-medium">{a.platform_b}</TableCell>
                    <TableCell className="text-right">{a.shared}</TableCell>
                    <TableCell className="text-right font-mono">{a.affinity_score.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No cross-platform data yet</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
