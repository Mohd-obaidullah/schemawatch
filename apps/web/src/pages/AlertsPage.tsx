import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchEvents, acknowledgeEvent, unacknowledgeEvent } from "@/api/client";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { SeverityBadge } from "@/components/ui/Badge";
import { DiffViewer } from "@/components/diff/DiffViewer";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/context/ToastContext";
import { formatRelativeTime } from "@/lib/utils";
import {
  Bell,
  CheckCircle,
  RotateCcw,
  Filter,
  CheckCheck,
  ChevronDown,
} from "lucide-react";
import type { DriftEvent, Severity } from "@/types";

export function AlertsPage(): React.ReactElement {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [selectedSeverity, setSelectedSeverity] = useState<Severity | "all">("all");
  const [selectedVendor, setSelectedVendor] = useState<string>("all");
  const [showAcknowledged, setShowAcknowledged] = useState<boolean>(false);
  const [limit, setLimit] = useState<number>(20);

  const {
    data: eventsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: [
      "events",
      {
        severity: selectedSeverity === "all" ? undefined : selectedSeverity,
        vendor: selectedVendor === "all" ? undefined : selectedVendor,
        acknowledged: showAcknowledged ? undefined : false,
        limit,
      },
    ],
    queryFn: () =>
      fetchEvents({
        severity: selectedSeverity === "all" ? undefined : selectedSeverity,
        vendor: selectedVendor === "all" ? undefined : selectedVendor,
        acknowledged: showAcknowledged ? undefined : false,
        limit,
      }),
    refetchInterval: 15000,
  });

  const ackMutation = useMutation({
    mutationFn: (id: number) => acknowledgeEvent(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["endpoints"] });
      toast({
        title: "Alert Acknowledged",
        description: `Alert #${id} marked as acknowledged.`,
        variant: "success",
      });
    },
    onError: (err) => {
      toast({
        title: "Failed to acknowledge",
        description: String(err),
        variant: "destructive",
      });
    },
  });

  const unackMutation = useMutation({
    mutationFn: (id: number) => unacknowledgeEvent(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["endpoints"] });
      toast({
        title: "Alert Reopened",
        description: `Alert #${id} marked as active.`,
        variant: "default",
      });
    },
    onError: (err) => {
      toast({
        title: "Failed to reopen",
        description: String(err),
        variant: "destructive",
      });
    },
  });

  const events = (eventsData?.items ?? []) as DriftEvent[];
  const totalCount = eventsData?.total ?? 0;
  const hasMore = events.length < totalCount;

  // Extract unique vendors for dropdown
  const vendors = Array.from(new Set(events.map((e) => e.vendor))).sort();

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Bell className="w-5 h-5 text-primary" />
            Contract Drift Alerts
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit log of all detected payload schema mutations, severity ratings, and resolution status.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <Card className="bg-card/40">
        <CardContent className="p-4 flex flex-wrap items-center justify-between gap-4">
          {/* Severity Chips */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-muted-foreground mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Severity:
            </span>
            {(["all", "breaking", "warning", "info"] as const).map((sev) => (
              <button
                key={sev}
                onClick={() => setSelectedSeverity(sev)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors ${
                  selectedSeverity === sev
                    ? sev === "breaking"
                      ? "bg-red-500 text-white font-semibold shadow-xs"
                      : sev === "warning"
                      ? "bg-amber-500 text-white font-semibold shadow-xs"
                      : sev === "info"
                      ? "bg-sky-500 text-white font-semibold shadow-xs"
                      : "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>

          {/* Vendor Filter & Acknowledged Toggle */}
          <div className="flex items-center gap-3">
            {/* Vendor Selector */}
            {vendors.length > 0 && (
              <div className="flex items-center gap-1 text-xs">
                <span className="text-muted-foreground">Vendor:</span>
                <select
                  value={selectedVendor}
                  onChange={(e) => setSelectedVendor(e.target.value)}
                  className="rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground focus:outline-hidden"
                >
                  <option value="all">All Vendors</option>
                  {vendors.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Acknowledged Toggle */}
            <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showAcknowledged}
                onChange={(e) => setShowAcknowledged(e.target.checked)}
                className="rounded border-input text-primary focus:ring-primary h-3.5 w-3.5"
              />
              <span>Include Acknowledged</span>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Alerts Feed */}
      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-900 dark:text-red-200">
          Error loading alerts: {String(error)}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : events.length === 0 ? (
        <Card className="py-12 text-center">
          <CardContent className="space-y-2">
            <CheckCheck className="w-8 h-8 text-emerald-500 mx-auto" />
            <p className="text-sm font-semibold">No drift alerts matching your criteria</p>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              All monitored endpoints are complying with their established schema baselines.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {events.map((event) => (
            <Card
              key={event.id}
              className={`transition-all hover:shadow-md ${
                event.acknowledged
                  ? "opacity-60 bg-muted/20 border-dashed"
                  : event.severity === "breaking"
                  ? "border-red-300/80 dark:border-red-900/60"
                  : event.severity === "warning"
                  ? "border-amber-300/80 dark:border-amber-900/60"
                  : "border-sky-300/80 dark:border-sky-900/60"
              }`}
            >
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 gap-2">
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={event.severity} />
                  <div>
                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                      <span className="capitalize">{event.vendor}</span>
                      <span className="font-mono text-xs text-muted-foreground font-normal">
                        {event.endpoint}
                      </span>
                    </CardTitle>
                    <CardDescription className="font-mono text-[11px] text-foreground font-medium">
                      {event.field_path} — {event.detail}
                    </CardDescription>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[11px] text-muted-foreground font-mono">
                    {formatRelativeTime(event.detected_at)}
                  </span>
                  {event.acknowledged ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => unackMutation.mutate(event.id)}
                      isLoading={unackMutation.isPending}
                    >
                      <RotateCcw className="w-3 h-3 mr-1 text-slate-500" />
                      Reopen
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs hover:bg-emerald-100 hover:text-emerald-900 dark:hover:bg-emerald-950 dark:hover:text-emerald-200"
                      onClick={() => ackMutation.mutate(event.id)}
                      isLoading={ackMutation.isPending}
                    >
                      <CheckCircle className="w-3 h-3 mr-1 text-emerald-600" />
                      Acknowledge
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent className="pt-0">
                <DiffViewer event={event} />
              </CardContent>
            </Card>
          ))}

          {/* Load More Pagination */}
          {hasMore && (
            <div className="pt-4 text-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setLimit((prev) => prev + 20)}
                className="gap-1.5"
              >
                <span>Load More Alerts</span>
                <ChevronDown className="w-3.5 h-3.5" />
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
