"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getResearchers, searchProfiles } from "@/lib/api";
import { Input } from "@/components/ui/input";
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
import { Search, DollarSign, Bug, Trophy } from "lucide-react";
import Link from "next/link";
import { useDebounce } from "@/lib/hooks";

const SORT_OPTIONS = [
  { value: "score", label: "Score" },
  { value: "earnings", label: "Earnings" },
  { value: "findings", label: "Findings" },
  { value: "platforms", label: "Platforms" },
  { value: "name", label: "Name" },
];

export default function ResearchersPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState("score");
  const limit = 24;
  const debouncedSearch = useDebounce(searchTerm, 300);

  const researchersQuery = useQuery({
    queryKey: ["researchers", page, sort],
    queryFn: () => getResearchers(page * limit, limit, sort),
    enabled: !debouncedSearch,
  });

  const searchQuery = useQuery({
    queryKey: ["search", debouncedSearch],
    queryFn: () => searchProfiles(debouncedSearch),
    enabled: !!debouncedSearch,
  });

  const isSearching = !!debouncedSearch;
  const loading = isSearching ? searchQuery.isLoading : researchersQuery.isLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Researchers</h1>
        <Select value={sort} onValueChange={(v) => { setSort(v); setPage(0); }}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>Sort: {o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search profiles by username..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setPage(0);
          }}
          className="pl-9"
        />
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : isSearching ? (
        searchQuery.data?.results.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {searchQuery.data.results.map((r) => (
              <Card key={r.profile_id} className="hover:border-primary/50 transition-colors">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium">{r.display_name || r.username}</p>
                      <p className="text-sm text-muted-foreground">@{r.username}</p>
                    </div>
                    <Badge variant="secondary">{r.platform_name}</Badge>
                  </div>
                  {r.researcher_id && (
                    <Link
                      href={`/researchers/${r.researcher_id}`}
                      className="mt-2 block text-sm text-primary hover:underline"
                    >
                      View researcher: {r.researcher_name}
                    </Link>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground">
            No profiles found for &quot;{debouncedSearch}&quot;
          </p>
        )
      ) : (
        <>
          {researchersQuery.data?.researchers.length ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {researchersQuery.data.researchers.map((r) => (
                <Link key={r.id} href={`/researchers/${r.id}`}>
                  <Card className="h-full hover:border-primary/50 transition-colors">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium">{r.canonical_name}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            {r.total_earnings > 0 && (
                              <span className="flex items-center gap-1 font-mono">
                                <DollarSign className="h-3 w-3" />
                                {r.total_earnings.toLocaleString()}
                              </span>
                            )}
                            {r.total_findings > 0 && (
                              <span className="flex items-center gap-1">
                                <Bug className="h-3 w-3" />
                                {r.total_findings} findings
                              </span>
                            )}
                            {r.top_score != null && r.top_score > 0 && (
                              <span className="flex items-center gap-1">
                                <Trophy className="h-3 w-3" />
                                {r.top_score.toFixed(1)}
                              </span>
                            )}
                          </div>
                        </div>
                        <Badge variant="outline">{r.platform_count} platform{r.platform_count !== 1 ? "s" : ""}</Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1">
                        {[...new Map(r.profiles.map((p) => [p.platform, p])).values()].map((p) => (
                          <Badge
                            key={p.platform}
                            variant="secondary"
                            className="text-xs"
                          >
                            {p.platform}: {p.username}
                          </Badge>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">
              No researchers found. Run some scrapes first.
            </p>
          )}

          {researchersQuery.data && researchersQuery.data.count >= limit && (
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
                disabled={researchersQuery.data.count < limit}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
