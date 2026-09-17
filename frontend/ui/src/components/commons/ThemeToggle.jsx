import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "shadcn/button";

// This app is client-rendered only (no SSR), so there is no hydration
// mismatch to guard against — resolvedTheme is available from first paint.
const ThemeToggle = () => {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
};

export default ThemeToggle;
