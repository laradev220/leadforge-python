"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "leadforge-theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  const [hydrated, setHydrated] = useState(false);

  // Initial hydration
  useEffect(() => {
    setHydrated(true);
    let initial: Theme = "light";
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (stored === "dark" || stored === "light") {
        initial = stored;
      } else if (typeof window !== "undefined" && window.matchMedia) {
        initial = window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";
      }
    } catch {
      // ignore
    }
    setThemeState(initial);
    applyClass(initial);
  }, []);

  function applyClass(t: Theme) {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (t === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }

  function setTheme(t: Theme) {
    setThemeState(t);
    applyClass(t);
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch {
      // ignore
    }
  }

  function toggle() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  // Prevent flash of unstyled content by ensuring class is on the html
  // element before paint. This is a soft guarantee — main impact is on
  // first load.
  useEffect(() => {
    if (!hydrated) return;
    applyClass(theme);
  }, [theme, hydrated]);

  return (
    <ThemeContext.Provider value={{ theme, toggle, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    // Safe fallback for components rendered outside the provider (e.g. SSR)
    return { theme: "light", toggle: () => {}, setTheme: () => {} };
  }
  return ctx;
}
