import React from "react";
import { useTheme } from "@/context/ThemeContext";
import { Moon, Sun, Monitor } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function ThemeToggle(): React.ReactElement {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center rounded-lg border bg-muted/30 p-0.5 text-muted-foreground">
      <Button
        variant="ghost"
        size="icon"
        className={`h-7 w-7 rounded-md ${theme === "light" ? "bg-background text-foreground shadow-xs" : ""}`}
        onClick={() => setTheme("light")}
        title="Light theme"
        aria-label="Light theme"
      >
        <Sun className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className={`h-7 w-7 rounded-md ${theme === "dark" ? "bg-background text-foreground shadow-xs" : ""}`}
        onClick={() => setTheme("dark")}
        title="Dark theme"
        aria-label="Dark theme"
      >
        <Moon className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className={`h-7 w-7 rounded-md ${theme === "system" ? "bg-background text-foreground shadow-xs" : ""}`}
        onClick={() => setTheme("system")}
        title="System theme"
        aria-label="System theme"
      >
        <Monitor className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
