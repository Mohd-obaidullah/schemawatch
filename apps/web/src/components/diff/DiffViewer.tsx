import React from "react";
import { SeverityBadge } from "@/components/ui/Badge";
import type { DriftEvent } from "@/types";
import { ArrowRight, FileDiff } from "lucide-react";

interface DiffViewerProps {
  event: DriftEvent;
  compact?: boolean;
}

export function DiffViewer({ event, compact = false }: DiffViewerProps): React.ReactElement {
  if (compact) {
    return (
      <div className="flex items-center gap-2 font-mono text-xs">
        <span className="font-semibold text-foreground">{event.field_path}:</span>
        <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 line-through">
          {event.was_value}
        </span>
        <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
        <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 font-medium">
          {event.now_value}
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card/60 overflow-hidden text-xs shadow-xs">
      <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/40">
        <div className="flex items-center gap-2">
          <FileDiff className="w-4 h-4 text-primary" />
          <span className="font-mono font-semibold text-foreground">{event.field_path}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-muted-foreground uppercase">{event.kind}</span>
          <SeverityBadge severity={event.severity} />
        </div>
      </div>

      <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* WAS box */}
        <div className="rounded-md border border-red-200 dark:border-red-900 bg-red-50/50 dark:bg-red-950/30 p-2.5">
          <div className="text-[10px] uppercase font-bold text-red-700 dark:text-red-400 mb-1 flex items-center justify-between">
            <span>Baseline / Expected</span>
            <span className="font-mono text-[10px] opacity-75">WAS</span>
          </div>
          <div className="font-mono text-xs text-red-950 dark:text-red-200 break-all font-medium">
            {event.was_value}
          </div>
        </div>

        {/* NOW box */}
        <div className="rounded-md border border-emerald-200 dark:border-emerald-900 bg-emerald-50/50 dark:bg-emerald-950/30 p-2.5">
          <div className="text-[10px] uppercase font-bold text-emerald-700 dark:text-emerald-400 mb-1 flex items-center justify-between">
            <span>Observed Drift</span>
            <span className="font-mono text-[10px] opacity-75">NOW</span>
          </div>
          <div className="font-mono text-xs text-emerald-950 dark:text-emerald-200 break-all font-medium">
            {event.now_value}
          </div>
        </div>
      </div>

      <div className="px-3 py-2 border-t bg-muted/20 text-muted-foreground text-[11px] flex items-center justify-between">
        <span>{event.detail}</span>
        <span className="font-mono text-[10px]">detected {new Date(event.detected_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}
