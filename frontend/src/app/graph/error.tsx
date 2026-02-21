"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

export default function GraphError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Graph error boundary caught:", error);
  }, [error]);

  const isWebGL = error.message?.toLowerCase().includes("webgl");

  return (
    <div className="flex items-center justify-center p-12">
      <Card className="max-w-md">
        <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
          <div className="rounded-lg bg-destructive/10 p-3">
            <AlertTriangle className="h-6 w-6 text-destructive" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">
              {isWebGL ? "WebGL not available" : "Graph failed to load"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {isWebGL
                ? "The graph explorer requires WebGL. Try a different browser or enable hardware acceleration."
                : error.message || "An unexpected error occurred loading the graph."}
            </p>
          </div>
          <Button onClick={reset} variant="outline">
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
