import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchEndpointById,
  fetchEndpointBaseline,
  fetchEvents,
  acceptEndpointBaseline,
  acknowledgeEvent,
  unacknowledgeEvent,
} from "@/api/client";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge, SeverityBadge } from "@/components/ui/Badge";
import { SchemaTree } from "@/components/schema/SchemaTree";
import { Dialog } from "@/components/ui/Dialog";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/context/ToastContext";
import { formatRelativeTime } from "@/lib/utils";
import {
  ArrowLeft,
  CheckCircle2,
  GitBranch,
  Layers,
  Clock,
  AlertTriangle,
  History,
  Check,
  RotateCcw,
} from "lucide-react";
import type { Endpoint, Baseline, DriftEvent } from "@/types";

export function EndpointDetailPage(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  const endpointId = Number(id);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [acceptDialogOpen, setAcceptDialogOpen] = useState(false);

  const {
    data: endpoint,
    isLoading: endpointLoading,
    error: endpointError,
  } = useQuery({
    queryKey: ["endpoint", endpointId],
    queryFn: () => fetchEndpointById(endpointId),
    enabled: !isNaN(endpointId),
  });

  const {
    data: baseline,
    isLoading: baselineLoading,
  } = useQuery({
    queryKey: ["endpointBaseline", endpointId],
    queryFn: () => fetchEndpointBaseline(endpointId),
    enabled: !isNaN(endpointId),
  });

  const {
    data: endpointEventsData,
    isLoading: eventsLoading,
  } = useQuery({
    queryKey: ["endpointEvents", endpointId],
    queryFn: () => fetchEvents({ endpoint_id: endpointId, limit: 50 }),
    enabled: !isNaN(endpointId),
  });

  const acceptMutation = useMutation({
    mutationFn: () => acceptEndpointBaseline(endpointId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["endpoint", endpointId] });
      queryClient.invalidateQueries({ queryKey: ["endpointBaseline", endpointId] });
      queryClient.invalidateQueries({ queryKey: ["endpointEvents", endpointId] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["endpoints"] });
      setAcceptDialogOpen(false);
      toast({
        title: "Baseline Updated",
        description: `Adopted new baseline v${data.new_baseline_version}. Closed ${data.events_acknowledged} active alert(s).`,
        variant: "success",
      });
    },
    onError: (err) => {
      toast({
        title: "Failed to accept baseline",
        description: String(err),
        variant: "destructive",
      });
    },
  });

  const ackMutation = useMutation({
    mutationFn: (eventId: number) => acknowledgeEvent(eventId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["endpointEvents", endpointId] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  const unackMutation = useMutation({
    mutationFn: (eventId: number) => unacknowledgeEvent(eventId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["endpointEvents", endpointId] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  if (endpointError) {
    return (
      <div className="space-y-4">
        <Link to="/" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
        </Link>
        <Card className="p-6 text-center text-sm text-red-500">
          Endpoint not found or error loading endpoint details.
        </Card>
      </div>
    );
  }

  const ep = endpoint as Endpoint | undefined;
  const base = baseline as Baseline | undefined;
  const events = (endpointEventsData?.items ?? []) as DriftEvent[];

  return (
    <div className="space-y-6">
      {/* Back button & Header */}
      <div className="space-y-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Overview</span>
        </Link>

        {endpointLoading ? (
          <Skeleton className="h-12 w-96" />
        ) : (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold tracking-tight text-foreground font-mono">
                  {ep?.endpoint}
                </h1>
                {ep && <StatusBadge status={ep.status} />}
              </div>
              <p className="text-xs text-muted-foreground flex items-center gap-2">
                <span className="capitalize font-semibold text-foreground">{ep?.vendor}</span>
                <span>•</span>
                <span>Endpoint ID #{ep?.id}</span>
                <span>•</span>
                <span>Observed {ep?.sample_count} live payload samples</span>
              </p>
            </div>

            <Button
              onClick={() => setAcceptDialogOpen(true)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs gap-1.5 shadow-sm"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Accept New Schema</span>
            </Button>
          </div>
        )}
      </div>

      {/* Endpoint Metadata Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Current Baseline
            </CardTitle>
            <GitBranch className="w-4 h-4 text-primary" />
          </CardHeader>
          <CardContent>
            {endpointLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <div className="text-xl font-bold font-mono">v{ep?.current_baseline_version}</div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Learned response shape</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Traffic Sample Count
            </CardTitle>
            <Layers className="w-4 h-4 text-primary" />
          </CardHeader>
          <CardContent>
            {endpointLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <div className="text-xl font-bold font-mono">{ep?.sample_count}</div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">Live requests evaluated</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Last Mutation Detected
            </CardTitle>
            <Clock className="w-4 h-4 text-primary" />
          </CardHeader>
          <CardContent>
            {endpointLoading ? (
              <Skeleton className="h-7 w-28" />
            ) : (
              <div className="text-xl font-bold font-mono">
                {ep ? formatRelativeTime(ep.updated_at) : "Never"}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground mt-1">
              Active open alerts: {ep?.open_alerts_count ?? 0}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Schema Tree Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-primary" />
            Learned Contract Schema (Baseline v{ep?.current_baseline_version})
          </CardTitle>
          <CardDescription>
            Type graph inferred from real-world responses. Fields marked with{" "}
            <span className="text-red-500 font-bold">*required</span> appeared in 100% of samples.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {baselineLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : base?.schema ? (
            <SchemaTree schema={base.schema} rootName="response_body" />
          ) : (
            <div className="p-6 text-center text-xs text-muted-foreground">
              No schema available for this baseline.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Drift History */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <History className="w-4 h-4 text-primary" />
            Drift History for this Endpoint
          </CardTitle>
          <CardDescription>
            Audit log of schema variances observed during live API traffic.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {eventsLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : events.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted-foreground">
              No drift events recorded for this endpoint.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground font-medium uppercase tracking-wider text-[10px]">
                    <th className="pb-3 pr-4">Severity</th>
                    <th className="pb-3 pr-4">Field Path</th>
                    <th className="pb-3 pr-4">Kind</th>
                    <th className="pb-3 pr-4">Mutation</th>
                    <th className="pb-3 pr-4">Detected</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {events.map((ev) => (
                    <tr key={ev.id} className="hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 pr-4">
                        <SeverityBadge severity={ev.severity} />
                      </td>
                      <td className="py-2.5 pr-4 font-mono font-medium">{ev.field_path}</td>
                      <td className="py-2.5 pr-4 font-mono text-[11px] text-muted-foreground">
                        {ev.kind}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs">
                        <span className="line-through text-red-600 dark:text-red-400 mr-1.5">
                          {ev.was_value}
                        </span>
                        <span>→</span>
                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold ml-1.5">
                          {ev.now_value}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-muted-foreground">
                        {formatRelativeTime(ev.detected_at)}
                      </td>
                      <td className="py-2.5 pr-4">
                        {ev.acknowledged ? (
                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                            Acknowledged
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 text-right">
                        {ev.acknowledged ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-[10px]"
                            onClick={() => unackMutation.mutate(ev.id)}
                            isLoading={unackMutation.isPending}
                          >
                            <RotateCcw className="w-3 h-3 mr-1" /> Reopen
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-[10px]"
                            onClick={() => ackMutation.mutate(ev.id)}
                            isLoading={ackMutation.isPending}
                          >
                            <Check className="w-3 h-3 mr-1 text-emerald-500" /> Ack
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Dialog for "Accept New Schema" */}
      <Dialog
        open={acceptDialogOpen}
        onOpenChange={setAcceptDialogOpen}
        title="Accept New Schema Baseline"
        description="Are you sure you want to adopt the most recently observed payload shape as the new baseline?"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Action consequences</p>
              <ul className="list-disc list-inside mt-1 space-y-0.5 opacity-90">
                <li>Increments baseline to version v{(ep?.current_baseline_version ?? 1) + 1}</li>
                <li>Automatically acknowledges all active drift alerts for this endpoint</li>
                <li>Future incoming payloads will be validated against this new schema</li>
              </ul>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAcceptDialogOpen(false)}
              disabled={acceptMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={() => acceptMutation.mutate()}
              isLoading={acceptMutation.isPending}
            >
              Confirm & Adopt Baseline
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
