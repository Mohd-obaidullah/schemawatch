/**
 * Live Server-Sent Events (SSE) Client
 *
 * NOTE ON ARCHITECTURE:
 * The standard browser `EventSource` interface does NOT support custom HTTP
 * headers (such as `Authorization: Bearer <API_TOKEN>`). Schemawatch endpoints
 * require bearer token authentication. We therefore implement a streaming SSE
 * client using browser `fetch()` with `ReadableStream` (`response.body.getReader()`).
 * This supports custom auth headers, exponential backoff reconnection, and full
 * heartbeat ping handling.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getStoredToken } from "./client";
import { useToast } from "@/context/ToastContext";
import type { ConnectionStatus, DriftEvent } from "@/types";

export type SSEEventListener = (event: DriftEvent) => void;
export type SSEStatusListener = (status: ConnectionStatus) => void;

export class SSEClient {
  private abortController: AbortController | null = null;
  private reconnectTimeout: number | null = null;
  private backoffMs = 1000;
  private maxBackoffMs = 16000;
  private isDisposed = false;
  private statusListeners = new Set<SSEStatusListener>();
  private eventListeners = new Set<SSEEventListener>();
  private currentStatus: ConnectionStatus = "disconnected";

  public onStatusChange(listener: SSEStatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.currentStatus);
    return () => this.statusListeners.delete(listener);
  }

  public onDriftEvent(listener: SSEEventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  private setStatus(status: ConnectionStatus): void {
    this.currentStatus = status;
    this.statusListeners.forEach((listener) => listener(status));
  }

  public connect(): void {
    if (this.isDisposed) return;
    this.cleanup();
    this.abortController = new AbortController();

    const token = getStoredToken();
    const headers: Record<string, string> = {
      Accept: "text/event-stream",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    this.setStatus(this.backoffMs > 1000 ? "reconnecting" : "reconnecting");

    fetch("/api/events/stream", {
      headers,
      signal: this.abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          if (response.status === 401) {
            this.setStatus("disconnected");
            if (typeof window !== "undefined") {
              window.dispatchEvent(new CustomEvent("schemawatch:unauthorized"));
            }
            return;
          }
          throw new Error(`SSE stream failed: HTTP ${response.status}`);
        }

        const body = response.body;
        if (!body) {
          throw new Error("Response body is null");
        }

        // Connection successful
        this.setStatus("connected");
        this.backoffMs = 1000; // Reset backoff

        const reader = body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        let isReading = true;
        while (isReading) {
          const { done, value } = await reader.read();
          if (done) {
            isReading = false;
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split("\n\n");
          buffer = messages.pop() ?? "";

          for (const rawMessage of messages) {
            this.parseAndDispatch(rawMessage.trim());
          }
        }
      })
      .catch((err) => {
        if (this.isDisposed || (err instanceof Error && err.name === "AbortError")) {
          return;
        }
        this.scheduleReconnect();
      });
  }

  private parseAndDispatch(rawMessage: string): void {
    if (!rawMessage) return;

    let eventType = "message";
    let dataStr = "";

    const lines = rawMessage.split("\n");
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataStr = line.slice(5).trim();
      }
    }

    if (eventType === "drift" && dataStr) {
      try {
        const driftEvent = JSON.parse(dataStr) as DriftEvent;
        this.eventListeners.forEach((listener) => listener(driftEvent));
      } catch (e) {
        console.error("Failed to parse drift event JSON:", e, dataStr);
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.isDisposed) return;
    this.setStatus("reconnecting");

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }

    this.reconnectTimeout = window.setTimeout(() => {
      this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);
      this.connect();
    }, this.backoffMs);
  }

  public cleanup(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  public dispose(): void {
    this.isDisposed = true;
    this.cleanup();
    this.setStatus("disconnected");
    this.statusListeners.clear();
    this.eventListeners.clear();
  }
}

// Global SSE client instance
let globalSSEClient: SSEClient | null = null;

export function getSSEClient(): SSEClient {
  if (!globalSSEClient) {
    globalSSEClient = new SSEClient();
  }
  return globalSSEClient;
}

/**
 * Hook for consuming live drift events, connection status, and query invalidation.
 */
export function useLiveEvents(): {
  status: ConnectionStatus;
  reconnect: () => void;
} {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const sseRef = useRef<SSEClient | null>(null);

  const reconnect = useCallback(() => {
    if (sseRef.current) {
      sseRef.current.connect();
    }
  }, []);

  useEffect(() => {
    const sse = getSSEClient();
    sseRef.current = sse;

    const unbindStatus = sse.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    const unbindEvent = sse.onDriftEvent((event) => {
      // Invalidate relevant TanStack queries so UI updates in real-time
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["endpoints"] });
      queryClient.invalidateQueries({ queryKey: ["endpoint", event.endpoint_id] });

      // Trigger notification toast
      const severity = event.severity;
      const isBreaking = severity === "breaking";
      toast({
        title: `${isBreaking ? "🚨 BREAKING" : severity === "warning" ? "⚠️ WARNING" : "ℹ️ INFO"} Drift Detected`,
        description: `${event.vendor} ${event.endpoint} — ${event.field_path}: ${event.detail}`,
        variant: isBreaking ? "breaking" : severity === "warning" ? "warning" : "info",
      });
    });

    sse.connect();

    return () => {
      unbindStatus();
      unbindEvent();
    };
  }, [queryClient, toast]);

  return { status, reconnect };
}
