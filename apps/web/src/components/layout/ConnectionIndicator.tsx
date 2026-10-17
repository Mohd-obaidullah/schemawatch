import React from "react";
import type { ConnectionStatus } from "@/types";
import { RefreshCw, Radio } from "lucide-react";

interface ConnectionIndicatorProps {
  status: ConnectionStatus;
  onReconnect?: () => void;
}

export function ConnectionIndicator({
  status,
  onReconnect,
}: ConnectionIndicatorProps): React.ReactElement {
  return (
    <div className="flex items-center gap-2 text-xs font-medium px-2.5 py-1 rounded-full border bg-background/50 backdrop-blur-xs">
      {status === "connected" && (
        <>
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="text-emerald-700 dark:text-emerald-400 font-semibold tracking-wide">
            LIVE
          </span>
        </>
      )}

      {status === "reconnecting" && (
        <>
          <RefreshCw className="w-3 h-3 text-amber-500 animate-spin" />
          <span className="text-amber-700 dark:text-amber-400">Reconnecting...</span>
        </>
      )}

      {status === "disconnected" && (
        <button
          onClick={onReconnect}
          className="flex items-center gap-1.5 text-red-600 dark:text-red-400 hover:underline"
          title="Click to reconnect"
        >
          <Radio className="w-3 h-3 text-red-500" />
          <span>Offline (click to retry)</span>
        </button>
      )}
    </div>
  );
}
