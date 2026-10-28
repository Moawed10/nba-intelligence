"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

export type ThemeChoice = "dark" | "light" | "system";
export const THEME_KEY = "nbai-theme";
const CHANGE_EVENT = "nbai-theme-change";
const ORDER: ThemeChoice[] = ["dark", "light", "system"];
const LABEL: Record<ThemeChoice, string> = { dark: "Dark", light: "Light", system: "System" };

/** Runs before first paint (see layout.tsx) so the page never flashes the wrong theme. */
export const themeScript = `(()=>{try{var c=localStorage.getItem("${THEME_KEY}")||"dark";var d=c==="dark"||(c==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){document.documentElement.classList.add("dark")}})()`;

export function readChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "system" ? stored : "dark";
  } catch {
    return "dark";
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

export function applyTheme(choice: ThemeChoice) {
  const dark =
    choice === "dark" ||
    (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function ThemeToggle() {
  const choice = useSyncExternalStore(subscribe, readChoice, () => "dark" as ThemeChoice);

  useEffect(() => {
    applyTheme(choice);
    if (choice !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [choice]);

  const next = ORDER[(ORDER.indexOf(choice) + 1) % ORDER.length];
  const Icon = choice === "dark" ? Moon : choice === "light" ? Sun : Monitor;

  return (
    <Button
      variant="ghost"
      size="icon"
      className="rounded-full"
      aria-label={`Theme: ${LABEL[choice]}. Switch to ${LABEL[next]}`}
      onClick={() => {
        try {
          localStorage.setItem(THEME_KEY, next);
        } catch {}
        applyTheme(next);
        window.dispatchEvent(new Event(CHANGE_EVENT));
      }}
    >
      <Icon aria-hidden className="size-5" />
    </Button>
  );
}
