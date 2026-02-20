"use client";

import { useQuery } from "@tanstack/react-query";
import { getAnalytics } from "@/lib/api";
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
import { Users, Globe, Camera, Link2 } from "lucide-react";

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number | undefined;
  icon: React.ElementType;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <div className="rounded-lg bg-primary/10 p-3">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold">
            {value !== undefined ? value.toLocaleString() : <Skeleton className="h-8 w-16" />}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["analytics"],
    queryFn: getAnalytics,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Researchers" value={data?.counts.researchers} icon={Users} />
        <StatCard label="Profiles" value={data?.counts.profiles} icon={Globe} />
        <StatCard label="Snapshots" value={data?.counts.snapshots} icon={Camera} />
        <StatCard label="Social Links" value={data?.counts.social_links} icon={Link2} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Top Researchers (Score)</CardTitle>
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
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="text-right">Platforms</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_by_score.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        <Link
                          href={`/researchers/${r.id}`}
                          className="text-primary hover:underline"
                        >
                          {r.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {r.score.toFixed(1)}
                      </TableCell>
                      <TableCell className="text-right">
                        {r.platform_count}
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
            <CardTitle>Top Earners</CardTitle>
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
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">Earnings</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_by_earnings.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        <Link
                          href={`/researchers/${r.id}`}
                          className="text-primary hover:underline"
                        >
                          {r.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ${r.total_earnings.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No earnings data yet</p>
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
              <ResponsiveContainer width="100%" height={280}>
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
                  <XAxis dataKey="num_platforms" />
                  <YAxis />
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
    </div>
  );
}
