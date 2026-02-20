"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import type { GraphData } from "@/types/phoenix";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Search, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";

const NODE_COLORS: Record<string, string> = {
  researcher: "#3b82f6",
  platform: "#10b981",
  profile: "#6b7280",
};

export default function GraphCanvas({ data }: { data: GraphData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState("");
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    researcher: true,
    platform: true,
    profile: true,
  });

  useEffect(() => {
    if (!containerRef.current || !data.nodes.length) return;

    const graph = new Graph();

    // Add nodes
    for (const node of data.nodes) {
      if (!graph.hasNode(node.id)) {
        graph.addNode(node.id, {
          label: node.label,
          size: node.size,
          color: NODE_COLORS[node.type] || "#6b7280",
          x: Math.random() * 100,
          y: Math.random() * 100,
          nodeType: node.type,
          score: node.score,
          platform: node.platform,
        });
      }
    }

    // Add edges
    for (const edge of data.edges) {
      if (
        graph.hasNode(edge.source) &&
        graph.hasNode(edge.target) &&
        !graph.hasEdge(edge.id)
      ) {
        graph.addEdge(edge.source, edge.target, {
          id: edge.id,
          color: "#333333",
          size: 0.5,
        });
      }
    }

    // Run ForceAtlas2 layout
    forceAtlas2.assign(graph, {
      iterations: 100,
      settings: {
        gravity: 1,
        scalingRatio: 10,
        barnesHutOptimize: graph.order > 500,
      },
    });

    graphRef.current = graph;

    const sigma = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: false,
      defaultEdgeColor: "#333333",
      defaultEdgeType: "line",
      labelFont: "var(--font-geist-sans)",
      labelColor: { color: "#e5e5e5" },
      labelSize: 12,
      labelRenderedSizeThreshold: 8,
    });

    sigmaRef.current = sigma;

    // Click handler
    sigma.on("clickNode", ({ node }) => {
      const attrs = graph.getNodeAttributes(node);
      if (attrs.nodeType === "researcher") {
        router.push(`/researchers/${node}`);
      }
    });

    // Hover handlers
    sigma.on("enterNode", ({ node }) => setHoveredNode(node));
    sigma.on("leaveNode", () => setHoveredNode(null));

    return () => {
      sigma.kill();
      sigmaRef.current = null;
      graphRef.current = null;
    };
  }, [data, router]);

  // Apply filters and search highlighting
  useEffect(() => {
    const sigma = sigmaRef.current;
    const graph = graphRef.current;
    if (!sigma || !graph) return;

    const searchLower = searchTerm.toLowerCase();

    sigma.setSetting("nodeReducer", (node, attrs) => {
      const nodeType = attrs.nodeType as string;
      if (!filters[nodeType as keyof typeof filters]) {
        return { ...attrs, hidden: true };
      }
      if (searchLower && !(attrs.label as string)?.toLowerCase().includes(searchLower)) {
        return { ...attrs, color: "#1a1a1a", label: "" };
      }
      if (hoveredNode) {
        if (node === hoveredNode || graph.hasEdge(node, hoveredNode) || graph.hasEdge(hoveredNode, node)) {
          return { ...attrs, zIndex: 1 };
        }
        return { ...attrs, color: "#1a1a1a", label: "" };
      }
      return attrs;
    });

    sigma.setSetting("edgeReducer", (_edge, attrs) => {
      return attrs;
    });

    sigma.refresh();
  }, [searchTerm, filters, hoveredNode]);

  const handleZoomIn = useCallback(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const camera = sigma.getCamera();
    camera.animatedZoom({ duration: 200 });
  }, []);

  const handleZoomOut = useCallback(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const camera = sigma.getCamera();
    camera.animatedUnzoom({ duration: 200 });
  }, []);

  const handleReset = useCallback(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const camera = sigma.getCamera();
    camera.animatedReset({ duration: 300 });
  }, []);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full bg-background" />

      {/* Floating controls */}
      <div className="absolute left-4 top-4 flex flex-col gap-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search nodes..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="h-8 w-48 bg-card pl-8 text-xs"
          />
        </div>
        <div className="flex gap-1">
          {(["researcher", "platform", "profile"] as const).map((type) => (
            <Badge
              key={type}
              variant={filters[type] ? "default" : "outline"}
              className="cursor-pointer text-xs"
              style={
                filters[type]
                  ? { backgroundColor: NODE_COLORS[type] }
                  : undefined
              }
              onClick={() =>
                setFilters((f) => ({ ...f, [type]: !f[type] }))
              }
            >
              {type}
            </Badge>
          ))}
        </div>
      </div>

      {/* Zoom controls */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-1">
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={handleZoomIn}>
          <ZoomIn className="h-3.5 w-3.5" />
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={handleZoomOut}>
          <ZoomOut className="h-3.5 w-3.5" />
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={handleReset}>
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Hover tooltip */}
      {hoveredNode && graphRef.current?.hasNode(hoveredNode) && (
        <div className="absolute right-4 top-4 rounded-md border bg-card p-3 text-sm shadow-lg">
          <p className="font-medium">
            {graphRef.current.getNodeAttribute(hoveredNode, "label")}
          </p>
          <p className="text-xs text-muted-foreground">
            Type: {graphRef.current.getNodeAttribute(hoveredNode, "nodeType")}
          </p>
          {graphRef.current.getNodeAttribute(hoveredNode, "score") != null && (
            <p className="text-xs text-muted-foreground">
              Score:{" "}
              {graphRef.current
                .getNodeAttribute(hoveredNode, "score")
                ?.toFixed(1)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
