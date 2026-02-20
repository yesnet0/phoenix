"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPlatforms,
  checkHealth,
  triggerScrape,
  getJobStatus,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Play, Activity, RefreshCw } from "lucide-react";
import type { ScrapeHealth, JobStatus } from "@/types/phoenix";

const STATUS_COLORS: Record<string, string> = {
  ok: "bg-green-500",
  empty: "bg-yellow-500",
  timeout: "bg-orange-500",
  captcha: "bg-red-500",
  error: "bg-red-500",
};

function JobTracker({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const { data } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJobStatus(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "SUCCESS" || status === "FAILURE") return false;
      return 3000;
    },
  });

  const isDone = data?.status === "SUCCESS" || data?.status === "FAILURE";

  return (
    <Card className="border-primary/30">
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          {!isDone && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
          <div className="flex-1">
            <p className="text-sm font-medium">Job {jobId.slice(0, 8)}...</p>
            <p className="text-xs text-muted-foreground">
              Status: {data?.status || "PENDING"}
            </p>
          </div>
          {isDone && data?.result && (
            <div className="text-right text-xs">
              <p>
                {data.result.profiles_scraped} scraped, {data.result.identities_resolved} resolved
              </p>
              <p className="text-muted-foreground">{data.result.duration_seconds}s</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ScrapePage() {
  const [healthData, setHealthData] = useState<ScrapeHealth | null>(null);
  const [triggerPlatform, setTriggerPlatform] = useState<string | null>(null);
  const [maxProfiles, setMaxProfiles] = useState("50");
  const [activeJobs, setActiveJobs] = useState<string[]>([]);
  const queryClient = useQueryClient();

  const { data: platformsData, isLoading: platformsLoading } = useQuery({
    queryKey: ["platforms"],
    queryFn: getPlatforms,
  });

  const healthMutation = useMutation({
    mutationFn: checkHealth,
    onSuccess: (data) => {
      setHealthData(data);
      toast.success(`Health check complete: ${data.ok}/${data.total} OK`);
    },
    onError: () => toast.error("Health check failed"),
  });

  const scrapeMutation = useMutation({
    mutationFn: ({
      platform,
      max,
    }: {
      platform: string;
      max: number;
    }) => triggerScrape(platform, max),
    onSuccess: (data) => {
      setActiveJobs((prev) => [...prev, data.job_id]);
      setTriggerPlatform(null);
      toast.success(`Scrape queued: ${data.job_id.slice(0, 8)}...`);
    },
    onError: () => toast.error("Failed to trigger scrape"),
  });

  const handleScrapeAll = useCallback(() => {
    if (!platformsData) return;
    for (const platform of platformsData.platforms) {
      scrapeMutation.mutate({ platform, max: parseInt(maxProfiles) });
    }
  }, [platformsData, maxProfiles, scrapeMutation]);

  const platforms = platformsData?.platforms || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Scrape Management</h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => healthMutation.mutate()}
            disabled={healthMutation.isPending}
          >
            {healthMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Activity className="mr-2 h-4 w-4" />
            )}
            Check Health
          </Button>
          <Button onClick={handleScrapeAll} disabled={!platforms.length}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Scrape All
          </Button>
        </div>
      </div>

      {/* Active jobs */}
      {activeJobs.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">Active Jobs</h2>
          {activeJobs.map((jobId) => (
            <JobTracker
              key={jobId}
              jobId={jobId}
              onDone={() =>
                queryClient.invalidateQueries({ queryKey: ["researchers"] })
              }
            />
          ))}
        </div>
      )}

      {/* Platform grid */}
      {platformsLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {platforms.map((platform) => {
            const health = healthData?.platforms[platform];
            const statusColor = health
              ? STATUS_COLORS[health.status] || "bg-gray-500"
              : "bg-gray-700";

            return (
              <Card
                key={platform}
                className="hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => setTriggerPlatform(platform)}
              >
                <CardContent className="flex items-center justify-between p-4">
                  <div>
                    <p className="text-sm font-medium">{platform}</p>
                    {health && (
                      <p className="text-xs text-muted-foreground">
                        {health.status}
                        {health.error && `: ${health.error.slice(0, 40)}...`}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${statusColor}`} />
                    <Play className="h-3 w-3 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Trigger dialog */}
      <Dialog
        open={!!triggerPlatform}
        onOpenChange={(open) => !open && setTriggerPlatform(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Scrape {triggerPlatform}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-muted-foreground">Max Profiles</label>
              <Select value={maxProfiles} onValueChange={setMaxProfiles}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              className="w-full"
              onClick={() =>
                triggerPlatform &&
                scrapeMutation.mutate({
                  platform: triggerPlatform,
                  max: parseInt(maxProfiles),
                })
              }
              disabled={scrapeMutation.isPending}
            >
              {scrapeMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Start Scrape
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
