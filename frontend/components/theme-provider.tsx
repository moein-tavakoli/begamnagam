"use client";

import { createContext, useContext, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { storedTheme, THEME_COLORS, THEME_STORAGE_KEY, type Theme } from "@/lib/theme";

const ThemeContext = createContext<{ theme: Theme; changing: boolean; toggle: (button: HTMLButtonElement) => void } | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");
  const [changing, setChanging] = useState(false);
  const preference = useRef<Theme | null>(null);
  const busy = useRef(false);
  const generation = useRef(0);
  const active = useRef<ViewTransition | null>(null);

  function apply(next: Theme) {
    document.documentElement.dataset.theme = next;
    // This meta belongs to the theme controller. React's hoisted metadata cache
    // keys on content, so mutating a React-owned light meta would duplicate it.
    const chrome = document.getElementById("app-theme-color") ?? document.head.appendChild(document.createElement("meta"));
    chrome.id = "app-theme-color";
    chrome.setAttribute("name", "theme-color");
    chrome.setAttribute("content", THEME_COLORS[next]);
    setTheme(next);
  }

  useLayoutEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    try { preference.current = storedTheme(localStorage.getItem(THEME_STORAGE_KEY)); } catch { /* Session-only choice still works. */ }
    apply(preference.current ?? (media.matches ? "dark" : "light"));
    const sync = () => {
      generation.current += 1;
      active.current?.skipTransition();
      apply(preference.current ?? (media.matches ? "dark" : "light"));
    };
    const system = () => { if (!preference.current) sync(); };
    const reduceMotion = () => { if (motion.matches) active.current?.skipTransition(); };
    const storage = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
      preference.current = storedTheme(event.newValue);
      sync();
    };
    media.addEventListener("change", system);
    motion.addEventListener("change", reduceMotion);
    window.addEventListener("storage", storage);
    return () => { generation.current += 1; active.current?.skipTransition(); media.removeEventListener("change", system); motion.removeEventListener("change", reduceMotion); window.removeEventListener("storage", storage); };
  }, []);

  function toggle(button: HTMLButtonElement) {
    if (busy.current) return;
    const next: Theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    const current = ++generation.current;
    const update = () => {
      if (generation.current !== current) return;
      preference.current = next;
      try { localStorage.setItem(THEME_STORAGE_KEY, next); } catch { /* Storage can be unavailable in private/embedded browsers. */ }
      // Theme visuals depend directly on this attribute, so the browser snapshot
      // sees the new colors synchronously without forcing a React render.
      apply(next);
    };
    if (!document.startViewTransition || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      update(); return;
    }

    const bounds = button.getBoundingClientRect();
    const x = bounds.left + bounds.width / 2, y = bounds.top + bounds.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)) + 4;
    busy.current = true; setChanging(true);
    document.documentElement.dataset.themeTransition = "active";
    void (async () => {
      try {
        const transition = document.startViewTransition(update);
        active.current = transition;
        void transition.finished.catch(() => undefined);
        await transition.ready;
        const reveal = document.documentElement.animate({
          clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`],
        }, { duration: 620, easing: "cubic-bezier(.4, 0, .2, 1)", fill: "both", pseudoElement: "::view-transition-new(root)" });
        await reveal.finished;
        await transition.finished;
      } catch {
        // A skipped snapshot or an unsupported pseudo-element must never prevent
        // the user's theme choice from taking effect.
        active.current?.skipTransition();
        update();
      } finally {
        active.current = null;
        delete document.documentElement.dataset.themeTransition;
        busy.current = false; setChanging(false);
      }
    })();
  }

  return <ThemeContext.Provider value={{ theme, changing, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("ThemeProvider is required");
  return value;
}
