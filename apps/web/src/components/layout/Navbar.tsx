import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, Bell, Settings, ShieldCheck, LogOut, KeyRound } from "lucide-react";
import { ConnectionIndicator } from "./ConnectionIndicator";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "@/context/AuthContext";
import { useLiveEvents } from "@/api/sse";
import { Button } from "@/components/ui/Button";
import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "@/api/client";

export function Navbar(): React.ReactElement {
  const location = useLocation();
  const { token, clearToken, devMode } = useAuth();
  const { status, reconnect } = useLiveEvents();

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 30000,
  });

  const activeAlerts = stats?.active_alerts_count ?? 0;

  const navItems = [
    {
      to: "/",
      label: "Overview",
      icon: Activity,
      active: location.pathname === "/" || location.pathname === "/overview",
    },
    {
      to: "/alerts",
      label: "Alerts",
      icon: Bell,
      badge: activeAlerts > 0 ? activeAlerts : undefined,
      active: location.pathname.startsWith("/alerts"),
    },
    {
      to: "/settings",
      label: "Settings",
      icon: Settings,
      active: location.pathname.startsWith("/settings"),
    },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur-md transition-colors">
      <div className="container flex h-14 items-center justify-between">
        {/* Brand & Nav links */}
        <div className="flex items-center gap-6 md:gap-8">
          <Link
            to="/"
            className="flex items-center gap-2.5 font-bold tracking-tight text-foreground hover:opacity-90 transition-opacity"
          >
            <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight leading-none">schemawatch</span>
              <span className="text-[10px] text-muted-foreground font-mono">drift monitor</span>
            </div>
          </Link>

          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    item.active
                      ? "bg-secondary text-foreground font-semibold"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                  {item.badge !== undefined && (
                    <span className="ml-1 inline-flex items-center justify-center px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-3">
          <ConnectionIndicator status={status} onReconnect={reconnect} />
          <ThemeToggle />

          {devMode && !token && (
            <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
              DEV MODE
            </span>
          )}

          {token ? (
            <Button
              variant="outline"
              size="sm"
              onClick={clearToken}
              className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
              title="Sign out (clears bearer token from sessionStorage)"
            >
              <LogOut className="w-3.5 h-3.5 mr-1" />
              <span>Sign out</span>
            </Button>
          ) : (
            <Link to="/token">
              <Button variant="outline" size="sm" className="h-8 px-2.5 text-xs">
                <KeyRound className="w-3.5 h-3.5 mr-1" />
                <span>API Token</span>
              </Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
