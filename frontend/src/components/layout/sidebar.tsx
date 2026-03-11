"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  GitGraph,
  Search,
  Users,
  Zap,
  Activity,
  Menu,
  Tag,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getHealth } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: BarChart3 },
  { href: "/graph", label: "Graph", icon: GitGraph },
  { href: "/researchers", label: "Researchers", icon: Search },
  { href: "/skills", label: "Skills", icon: Tag },
  { href: "/profiles", label: "Profiles", icon: Users },
  { href: "/scrape", label: "Scrape", icon: Zap },
];

function NavLinks({ onClick }: { onClick?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active =
          item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onClick}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function HealthIndicator() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });
  const ok = data?.neo4j === "connected";
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Activity className="h-3 w-3" />
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          ok ? "bg-green-500" : data ? "bg-red-500" : "bg-yellow-500"
        )}
      />
      {ok ? "Neo4j connected" : data ? "Neo4j disconnected" : "Checking..."}
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-56 md:flex-col md:border-r md:bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/" className="text-lg font-bold tracking-tight">
          Phoenix
        </Link>
      </div>
      <div className="flex-1 px-3 py-4">
        <NavLinks />
      </div>
      <div className="border-t px-4 py-3">
        <HealthIndicator />
      </div>
    </aside>
  );
}

export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="flex h-14 items-center gap-4 border-b bg-card px-4 md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-56 p-4">
          <div className="mb-6 text-lg font-bold">Phoenix</div>
          <NavLinks onClick={() => setOpen(false)} />
          <div className="mt-auto pt-4">
            <HealthIndicator />
          </div>
        </SheetContent>
      </Sheet>
      <span className="text-lg font-bold">Phoenix</span>
    </header>
  );
}
