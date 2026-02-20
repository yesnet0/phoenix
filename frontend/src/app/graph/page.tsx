"use client";

import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { getGraphData } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

const GraphCanvas = dynamic(() => import("@/components/graph/graph-canvas"), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full" />,
});

export default function GraphPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["graph"],
    queryFn: getGraphData,
  });

  return (
    <div className="flex h-full flex-col -m-6">
      <div className="flex items-center justify-between border-b bg-card px-6 py-3">
        <h1 className="text-lg font-bold">Graph Explorer</h1>
        {data && (
          <p className="text-xs text-muted-foreground">
            {data.nodes.length} nodes, {data.edges.length} edges
          </p>
        )}
      </div>
      <div className="relative flex-1">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Skeleton className="h-64 w-64 rounded-full" />
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Failed to load graph data
          </div>
        ) : data ? (
          <GraphCanvas data={data} />
        ) : null}
      </div>
    </div>
  );
}
