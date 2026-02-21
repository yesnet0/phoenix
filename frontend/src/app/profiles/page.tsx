"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getProfiles } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ExternalLink } from "lucide-react";
import Link from "next/link";

const SORT_OPTIONS = [
  { value: "earnings", label: "Top Earnings" },
  { value: "findings", label: "Most Findings" },
  { value: "score", label: "Highest Score" },
  { value: "rank", label: "Best Rank" },
  { value: "username", label: "Username A-Z" },
];

export default function ProfilesPage() {
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState("earnings");
  const [platform, setPlatform] = useState<string>("all");
  const limit = 50;

  const { data, isLoading } = useQuery({
    queryKey: ["profiles", page, sort, platform],
    queryFn: () =>
      getProfiles(
        page * limit,
        limit,
        platform === "all" ? undefined : platform,
        sort
      ),
  });

  const profiles = data?.profiles || [];
  const platforms = data?.platforms || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Profiles</h1>
        <div className="flex gap-2">
          <Select value={platform} onValueChange={(v) => { setPlatform(v); setPage(0); }}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="All platforms" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All platforms</SelectItem>
              {platforms.map((p) => (
                <SelectItem key={p} value={p}>{p}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sort} onValueChange={(v) => { setSort(v); setPage(0); }}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : profiles.length ? (
        <div className="space-y-2">
          {/* Table header */}
          <div className="grid grid-cols-12 gap-2 px-4 py-2 text-xs font-medium text-muted-foreground">
            <div className="col-span-3">Researcher</div>
            <div className="col-span-2">Platform</div>
            <div className="col-span-1 text-right">Rank</div>
            <div className="col-span-1 text-right">Score</div>
            <div className="col-span-2 text-right">Earnings</div>
            <div className="col-span-1 text-right">Findings</div>
            <div className="col-span-2 text-right">Severity</div>
          </div>

          {profiles.map((p) => (
            <Card key={p.profile_id} className="hover:border-primary/50 transition-colors">
              <CardContent className="grid grid-cols-12 items-center gap-2 p-4">
                {/* Name + link */}
                <div className="col-span-3">
                  <div className="flex items-center gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-sm">
                        {p.display_name || p.username}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">@{p.username}</p>
                    </div>
                    {p.profile_url && (
                      <a href={p.profile_url} target="_blank" rel="noopener noreferrer"
                        className="shrink-0 text-muted-foreground hover:text-foreground">
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  {p.researcher_id && (
                    <Link
                      href={`/researchers/${p.researcher_id}`}
                      className="text-xs text-primary hover:underline"
                    >
                      {p.researcher_name}
                    </Link>
                  )}
                </div>

                {/* Platform */}
                <div className="col-span-2">
                  <Badge variant="secondary" className="text-xs">{p.platform_name}</Badge>
                </div>

                {/* Rank */}
                <div className="col-span-1 text-right font-mono text-sm">
                  {p.rank != null ? `#${p.rank}` : "-"}
                </div>

                {/* Score */}
                <div className="col-span-1 text-right font-mono text-sm">
                  {p.score != null ? p.score.toFixed(1) : "-"}
                </div>

                {/* Earnings */}
                <div className="col-span-2 text-right font-mono text-sm">
                  {p.earnings != null ? `$${p.earnings.toLocaleString()}` : "-"}
                </div>

                {/* Findings */}
                <div className="col-span-1 text-right font-mono text-sm">
                  {p.findings != null ? p.findings : "-"}
                </div>

                {/* Severity */}
                <div className="col-span-2 flex justify-end gap-1">
                  {p.critical != null && p.critical > 0 && (
                    <Badge className="bg-red-500/20 text-red-400 text-xs px-1">C:{p.critical}</Badge>
                  )}
                  {p.high != null && p.high > 0 && (
                    <Badge className="bg-orange-500/20 text-orange-400 text-xs px-1">H:{p.high}</Badge>
                  )}
                  {p.medium != null && p.medium > 0 && (
                    <Badge className="bg-yellow-500/20 text-yellow-400 text-xs px-1">M:{p.medium}</Badge>
                  )}
                  {p.low != null && p.low > 0 && (
                    <Badge className="bg-blue-500/20 text-blue-400 text-xs px-1">L:{p.low}</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground">No profiles found.</p>
      )}

      {/* Pagination */}
      {data && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">Page {page + 1}</span>
          <Button
            variant="outline"
            size="sm"
            disabled={data.count < limit}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
