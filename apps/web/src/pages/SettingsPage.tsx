import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchConfig } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  Settings,
  Shield,
  Bell,
  Database,
  Sliders,
  CheckCircle2,
  XCircle,
  KeyRound,
  LogOut,
} from "lucide-react";
import type { AppConfig } from "@/types";

export function SettingsPage(): React.ReactElement {
  const { token, clearToken, setToken } = useAuth();
  const [newToken, setNewToken] = React.useState("");

  const {
    data: config,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
  });

  const cfg = config as AppConfig | undefined;

  const handleUpdateToken = (e: React.FormEvent): void => {
    e.preventDefault();
    if (newToken.trim()) {
      setToken(newToken.trim());
      setNewToken("");
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Settings className="w-5 h-5 text-primary" />
          System Settings & Configuration
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Read-only runtime engine configuration inspected from <code className="font-mono">/api/config</code>.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-900 dark:text-red-200">
          Error loading runtime configuration: {String(error)}
        </div>
      )}

      {/* Runtime Configuration Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Detection Engine Parameters */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary" />
              Watchdog Engine Parameters
            </CardTitle>
            <CardDescription>
              Tuning parameters for schema learning and drift detection.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between py-1 border-b border-border/40">
                  <span className="text-muted-foreground">Learning Sample Threshold</span>
                  <span className="font-mono font-semibold">{cfg?.learn_samples} samples</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-border/40">
                  <span className="text-muted-foreground">Post-learning Sampling Rate</span>
                  <span className="font-mono font-semibold">
                    {cfg?.sample_rate ? `${cfg.sample_rate * 100}%` : "100%"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-border/40">
                  <span className="text-muted-foreground">Alert Dedupe Cooldown</span>
                  <span className="font-mono font-semibold">{cfg?.cooldown_seconds}s</span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-muted-foreground">Minimum Alert Severity</span>
                  <span className="font-mono font-semibold uppercase">{cfg?.min_alert_severity}</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Persistence & Security */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Database className="w-4 h-4 text-primary" />
              Persistence & Security Mode
            </CardTitle>
            <CardDescription>
              Backend persistence layer and environment access profile.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between py-1 border-b border-border/40">
                  <span className="text-muted-foreground">Database Storage Type</span>
                  <span className="font-mono font-semibold uppercase">{cfg?.database_type}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-border/40">
                  <span className="text-muted-foreground">Developer Mode (Dev Bypass)</span>
                  <span
                    className={`font-semibold ${
                      cfg?.dev_mode ? "text-amber-500" : "text-emerald-500"
                    }`}
                  >
                    {cfg?.dev_mode ? "Enabled" : "Disabled (Enforced)"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-muted-foreground">Data Privacy Redaction</span>
                  <span className="text-emerald-500 font-semibold flex items-center gap-1">
                    <Shield className="w-3.5 h-3.5" /> Zero Payload Leaks
                  </span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Alert Dispatch Channels */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Bell className="w-4 h-4 text-primary" />
              Alert Dispatch Integrations
            </CardTitle>
            <CardDescription>
              Channel delivery status. Configured via environment variables; webhook secrets are
              never exposed.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-12 w-full" />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="p-3 rounded-lg border bg-muted/20 flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-foreground">Slack Incoming Webhooks</p>
                    <p className="text-[11px] text-muted-foreground">
                      Dispatches formatted color-coded attachments
                    </p>
                  </div>
                  {cfg?.slack_configured ? (
                    <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                      <CheckCircle2 className="w-4 h-4" /> Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-muted-foreground text-[11px]">
                      <XCircle className="w-4 h-4" /> Not Configured
                    </span>
                  )}
                </div>

                <div className="p-3 rounded-lg border bg-muted/20 flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-foreground">Generic Alert Webhook</p>
                    <p className="text-[11px] text-muted-foreground">
                      HTTP POST webhook receiver with HMAC signature
                    </p>
                  </div>
                  {cfg?.webhook_configured ? (
                    <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                      <CheckCircle2 className="w-4 h-4" /> Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-muted-foreground text-[11px]">
                      <XCircle className="w-4 h-4" /> Not Configured
                    </span>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Client Token Management */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-primary" />
            Dashboard Bearer Authentication Token
          </CardTitle>
          <CardDescription>
            Manage the active API Bearer token stored in browser <code className="font-mono">sessionStorage</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between text-xs p-3 rounded-lg border bg-muted/20">
            <div>
              <p className="font-semibold text-foreground">
                Active Session Token:{" "}
                <span className="font-mono text-muted-foreground font-normal">
                  {token ? `${token.slice(0, 4)}••••••••${token.slice(-4)}` : "None (Dev Mode)"}
                </span>
              </p>
              <p className="text-[11px] text-muted-foreground">
                Sent as <code className="font-mono">Authorization: Bearer ...</code> on all API calls.
              </p>
            </div>
            {token && (
              <Button variant="outline" size="sm" onClick={clearToken} className="h-8 text-xs">
                <LogOut className="w-3.5 h-3.5 mr-1" /> Clear Token
              </Button>
            )}
          </div>

          <form onSubmit={handleUpdateToken} className="flex gap-2">
            <input
              type="password"
              placeholder="Update Bearer Token..."
              value={newToken}
              onChange={(e) => setNewToken(e.target.value)}
              className="flex-1 rounded-md border border-input bg-background px-3 py-1 text-xs"
            />
            <Button type="submit" size="sm" disabled={!newToken.trim()} className="text-xs">
              Save Token
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
