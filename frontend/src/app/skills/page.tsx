"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSkillDistribution, getResearchersBySkill } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Tag } from "lucide-react";
import Link from "next/link";

function formatScore(score: number): string {
  if (score >= 1_000_000) return `${(score / 1_000_000).toFixed(1)}M`;
  if (score >= 1_000) return `${(score / 1_000).toFixed(1)}K`;
  return score.toFixed(0);
}

export default function SkillsPage() {
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);

  const distributionQuery = useQuery({
    queryKey: ["skill-distribution"],
    queryFn: getSkillDistribution,
  });

  const researchersQuery = useQuery({
    queryKey: ["skill-researchers", selectedSkill],
    queryFn: () => getResearchersBySkill(selectedSkill!, 0, 50),
    enabled: !!selectedSkill,
  });

  const distribution = distributionQuery.data?.distribution ?? [];
  const chartData = distribution
    .slice()
    .sort((a, b) => a.researcher_count - b.researcher_count);

  const totalSkills = distribution.length;
  const totalTagged = distribution.reduce(
    (sum, s) => sum + s.researcher_count,
    0
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Skills</h1>
          {totalSkills > 0 && (
            <Badge variant="outline" className="text-xs">
              {totalSkills} skills across {totalTagged} researcher tags
            </Badge>
          )}
        </div>
        {selectedSkill && (
          <button
            onClick={() => setSelectedSkill(null)}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear selection
          </button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-5 w-5" />
            Skill Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          {distributionQuery.isLoading ? (
            <Skeleton className="h-[400px] w-full" />
          ) : chartData.length ? (
            <div className="max-h-[600px] overflow-y-auto">
              <ResponsiveContainer
                width="100%"
                height={Math.max(300, chartData.length * 28)}
              >
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ left: 120 }}
                >
                  <XAxis type="number" />
                  <YAxis
                    type="category"
                    dataKey="skill"
                    width={115}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(value: number | undefined) => [value ?? 0, "Researchers"]}
                    cursor={{ fill: "hsl(var(--muted))" }}
                  />
                  <Bar
                    dataKey="researcher_count"
                    radius={[0, 4, 4, 0]}
                    onClick={(_data, index) => {
                      const skill = chartData[index]?.skill;
                      if (skill) setSelectedSkill(skill);
                    }}
                    className="cursor-pointer"
                  >
                    {chartData.map((entry) => (
                      <Cell
                        key={entry.skill}
                        fill={
                          entry.skill === selectedSkill
                            ? "hsl(var(--primary))"
                            : "hsl(var(--chart-1))"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No skill data yet. Run scrapes to collect researcher skills.
            </p>
          )}
        </CardContent>
      </Card>

      {selectedSkill && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Researchers with
              <Badge variant="secondary">{selectedSkill}</Badge>
              {researchersQuery.data && (
                <span className="text-sm font-normal text-muted-foreground">
                  ({researchersQuery.data.count} total)
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {researchersQuery.isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : researchersQuery.data?.researchers.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8">#</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="text-right">Profiles</TableHead>
                    <TableHead>Platforms</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {researchersQuery.data.researchers.map((r, i) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-muted-foreground">
                        {i + 1}
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/researchers/${r.id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {r.canonical_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatScore(r.composite_score)}
                      </TableCell>
                      <TableCell className="text-right">
                        {r.profile_count > 1 ? (
                          <Badge variant="secondary" className="text-xs">
                            {r.profile_count}
                          </Badge>
                        ) : (
                          r.profile_count
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {r.profiles.map((p) => (
                            <Badge
                              key={`${p.platform}-${p.username}`}
                              variant="outline"
                              className="text-xs"
                            >
                              {p.platform}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">
                No researchers found with skill &quot;{selectedSkill}&quot;
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
