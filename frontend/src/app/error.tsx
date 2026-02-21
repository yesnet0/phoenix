"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Phoenix error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center p-12">
      <Card className="max-w-md">
        <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
          <div className="rounded-lg bg-destructive/10 p-3">
            <AlertTriangle className="h-6 w-6 text-destructive" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Something went wrong</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {error.message || "An unexpected error occurred."}
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
