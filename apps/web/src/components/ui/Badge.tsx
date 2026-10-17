import React from "react";
import { cn } from "@/lib/utils";
import type { Severity, EndpointStatus } from "@/types";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "outline" | "breaking" | "warning" | "info" | "success" | "muted";
}

export function Badge({
  className,
  variant = "default",
  children,
  ...props
}: BadgeProps): React.ReactElement {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium tracking-wide transition-colors",
        variant === "default" && "bg-primary text-primary-foreground",
        variant === "secondary" && "bg-secondary text-secondary-foreground",
        variant === "outline" && "border border-border text-foreground",
        variant === "breaking" &&
          "bg-red-100 text-red-800 border border-red-300 dark:bg-red-950/60 dark:text-red-300 dark:border-red-800",
        variant === "warning" &&
          "bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800",
        variant === "info" &&
          "bg-sky-100 text-sky-800 border border-sky-300 dark:bg-sky-950/60 dark:text-sky-300 dark:border-sky-800",
        variant === "success" &&
          "bg-emerald-100 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800",
        variant === "muted" &&
          "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }): React.ReactElement {
  return (
    <Badge variant={severity} className="uppercase font-semibold text-[10px] tracking-wider">
      {severity}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: EndpointStatus }): React.ReactElement {
  if (status === "healthy") {
    return (
      <Badge variant="success" className="gap-1.5 font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-subtle" />
        Healthy
      </Badge>
    );
  }
  if (status === "drifting") {
    return (
      <Badge variant="warning" className="gap-1.5 font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        Drifting
      </Badge>
    );
  }
  return (
    <Badge variant="breaking" className="gap-1.5 font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      Broken
    </Badge>
  );
}
