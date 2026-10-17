import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchEndpoints, fetchStats } from "@/api/client";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatRelativeTime } from "@/lib/utils";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Info,
  Server,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import type { Endpoint } from "@/types";

export function OverviewPage(): React.ReactElement {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 15000,
  });

  const {
    data: endpointsData,
    isLoading: endpointsLoading,
  } = useQuery({
    queryKey: ["endpoints"],
    queryFn: () => fetchEndpoints({ limit: 50 }),
    refetchInterval: 15000,
  });

  const endpoints = (endpointsData?.items ?? []) as Endpoint[];

  const chartData = (stats?.alerts_per_hour ?? []).map((h) => {
    // Format hour string (e.g. "2026-10-17T18:00:00" -> "18:00")
    let label = h.hour;
    try {
      const d = new Date(h.hour);
      if (!isNaN(d.getTime())) {
        label = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
      }
    } catch {
      // keep raw
    }
    return {
      hour: label,
      Breaking: h.breaking,
      Warning: h.warning,
      Info: h.info,
      Total: h.count,
    };
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Dashboard Overview</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Real-time API contract monitoring and schema drift intelligence across third-party vendors.
        </p>
      </div>

      {statsError && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-900 dark:text-red-200 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>Failed to load server stats. Please verify your bearer token in settings.</span>
        </div>
      )}

      {/* Stat Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Endpoints */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Monitored Endpoints
            </CardTitle>
            <Server className="w-4 h-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold font-mono">{stats?.total_endpoints ?? 0}</div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Live traffic observed</p>
          </CardContent>
        </Card>

        {/* Breaking Alerts */}
        <Card className="hover:shadow-md transition-shadow border-l-4 border-l-red-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Breaking Alerts
            </CardTitle>
            <AlertCircle className="w-4 h-4 text-red-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold font-mono text-red-600 dark:text-red-400">
                {stats?.breaking_alerts_count ?? 0}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Type or nullable breaking changes</p>
          </CardContent>
        </Card>

        {/* Warnings */}
        <Card className="hover:shadow-md transition-shadow border-l-4 border-l-amber-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Warning Alerts
            </CardTitle>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">
                {stats?.warning_alerts_count ?? 0}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Enum drift or non-breaking mutations</p>
          </CardContent>
        </Card>

        {/* Info Alerts */}
        <Card className="hover:shadow-md transition-shadow border-l-4 border-l-sky-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Informational
            </CardTitle>
            <Info className="w-4 h-4 text-sky-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold font-mono text-sky-600 dark:text-sky-400">
                {stats?.info_alerts_count ?? 0}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">New fields added / schema growth</p>
          </CardContent>
        </Card>
      </div>

      {/* Chart: Alerts per hour */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              Contract Drift Activity (Last 12 Hours)
            </CardTitle>
            <CardDescription>
              Volume of detected schema changes categorized by severity level.
            </CardDescription>
          </div>
          <Link
            to="/alerts"
            className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
          >
            <span>View feed</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </CardHeader>
        <CardContent>
          {statsLoading ? (
            <Skeleton className="h-[220px] w-full" />
          ) : chartData.length > 0 ? (
            <div className="h-[220px] w-full pt-2">
              <ResponsiveContainer width="100%" height={220} minHeight={220}>
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
                  <XAxis dataKey="hour" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis fontSize={10} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "rgba(15, 23, 42, 0.9)",
                      borderColor: "rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      color: "#fff",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
                  <Bar dataKey="Breaking" fill="#EF4444" stackId="a" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="Warning" fill="#F59E0B" stackId="a" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="Info" fill="#2F80ED" stackId="a" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
              No alerts recorded in the last 12 hours.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Endpoints Health Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" />
              Endpoint Health Status
            </CardTitle>
            <CardDescription>
              All registered vendor API endpoints and active baseline versions.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          {endpointsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : endpoints.length === 0 ? (
            <div className="text-center py-8 text-xs text-muted-foreground">
              No endpoints monitored yet. Seed the database or ingest traffic to begin.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground font-medium uppercase tracking-wider text-[10px]">
                    <th className="pb-3 pr-4">Vendor</th>
                    <th className="pb-3 pr-4">Endpoint</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 pr-4">Samples</th>
                    <th className="pb-3 pr-4">Baseline Version</th>
                    <th className="pb-3 pr-4">Last Activity</th>
                    <th className="pb-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {endpoints.map((ep) => (
                    <tr key={ep.id} className="hover:bg-muted/30 transition-colors">
                      <td className="py-3 pr-4 font-semibold capitalize text-foreground">
                        {ep.vendor}
                      </td>
                      <td className="py-3 pr-4 font-mono font-medium text-foreground">
                        {ep.endpoint}
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={ep.status} />
                      </td>
                      <td className="py-3 pr-4 font-mono text-muted-foreground">
                        {ep.sample_count}
                      </td>
                      <td className="py-3 pr-4 font-mono">
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold">
                          v{ep.current_baseline_version}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatRelativeTime(ep.updated_at)}
                      </td>
                      <td className="py-3 text-right">
                        <Link
                          to={`/endpoints/${ep.id}`}
                          className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                        >
                          <span>Inspect</span>
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
