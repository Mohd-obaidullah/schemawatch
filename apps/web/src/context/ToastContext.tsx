import React, { createContext, useContext, useState, useCallback } from "react";
import { AlertCircle, AlertTriangle, CheckCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToastVariant = "default" | "breaking" | "warning" | "info" | "success" | "destructive";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastContextType {
  toast: (item: Omit<ToastItem, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, description, variant = "default" }: Omit<ToastItem, "id">) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const newItem: ToastItem = { id, title, description, variant };
      setToasts((prev) => [...prev.slice(-4), newItem]);

      setTimeout(() => {
        removeToast(id);
      }, 5000);
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toast, removeToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto flex items-start gap-3 p-4 rounded-lg shadow-lg border text-sm backdrop-blur-md transition-all duration-200 animate-in fade-in slide-in-from-bottom-2",
              t.variant === "breaking" || t.variant === "destructive"
                ? "bg-red-50/95 border-red-200 text-red-900 dark:bg-red-950/95 dark:border-red-800 dark:text-red-100"
                : t.variant === "warning"
                ? "bg-amber-50/95 border-amber-200 text-amber-900 dark:bg-amber-950/95 dark:border-amber-800 dark:text-amber-100"
                : t.variant === "info"
                ? "bg-sky-50/95 border-sky-200 text-sky-900 dark:bg-sky-950/95 dark:border-sky-800 dark:text-sky-100"
                : t.variant === "success"
                ? "bg-emerald-50/95 border-emerald-200 text-emerald-900 dark:bg-emerald-950/95 dark:border-emerald-800 dark:text-emerald-100"
                : "bg-white/95 border-slate-200 text-slate-900 dark:bg-slate-900/95 dark:border-slate-800 dark:text-slate-100"
            )}
          >
            <div className="shrink-0 mt-0.5">
              {t.variant === "breaking" || t.variant === "destructive" ? (
                <AlertCircle className="w-4 h-4 text-red-500" />
              ) : t.variant === "warning" ? (
                <AlertTriangle className="w-4 h-4 text-amber-500" />
              ) : t.variant === "info" ? (
                <Info className="w-4 h-4 text-sky-500" />
              ) : (
                <CheckCircle className="w-4 h-4 text-emerald-500" />
              )}
            </div>
            <div className="flex-1 space-y-1">
              <p className="font-semibold text-xs tracking-tight">{t.title}</p>
              {t.description && (
                <p className="text-xs opacity-90 leading-relaxed">{t.description}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(t.id)}
              className="shrink-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5"
              aria-label="Close notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextType {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
