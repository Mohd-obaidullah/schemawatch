import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { KeyRound, ShieldCheck, CheckCircle2 } from "lucide-react";

export function TokenPage(): React.ReactElement {
  const { token, setToken, devMode } = useAuth();
  const [inputVal, setInputVal] = useState(token || "");
  const [submitted, setSubmitted] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (inputVal.trim()) {
      setToken(inputVal.trim());
      setSubmitted(true);
      setTimeout(() => navigate("/"), 400);
    } else if (devMode) {
      navigate("/");
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-xl border-border/80">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary mb-2">
            <KeyRound className="w-6 h-6" />
          </div>
          <CardTitle className="text-xl">schemawatch Access</CardTitle>
          <CardDescription>
            Enter your API Bearer Token to authenticate with the dashboard.
          </CardDescription>
        </CardHeader>

        <CardContent>
          {devMode && (
            <div className="mb-5 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Developer Mode Enabled</p>
                <p className="opacity-90">
                  Authentication is bypassed on the server (SCHEMAWATCH_DEV_MODE=true). You can
                  proceed without a token or set one below.
                </p>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="token-input" className="text-xs font-semibold text-foreground">
                Bearer Token
              </label>
              <Input
                id="token-input"
                type="password"
                placeholder="sk_live_... or schemawatch token"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                autoFocus
              />
              <p className="text-[11px] text-muted-foreground">
                Token is stored in <code className="bg-muted px-1 py-0.5 rounded font-mono">sessionStorage</code> only and cleared on 401 or sign-out.
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              <Button type="submit" className="w-full">
                {submitted ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-300" />
                    Authenticated!
                  </>
                ) : (
                  "Continue to Dashboard"
                )}
              </Button>
            </div>

            {devMode && (
              <Button
                type="button"
                variant="ghost"
                className="w-full text-xs text-muted-foreground"
                onClick={() => navigate("/")}
              >
                Skip authentication (Dev Mode)
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
