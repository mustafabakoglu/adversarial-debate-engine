import { useCallback, useEffect, useState } from "react";

import { keyboard } from "./sound";

/**
 * The two reader-facing preferences, both persisted: colour theme and whether the
 * typing makes a sound.
 *
 * `system` is a real third theme state rather than a default that resolves to one
 * of the other two, so a reader who switches their OS to dark at sunset gets dark
 * without touching this app again.
 */
export type ThemeChoice = "system" | "light" | "dark";

const THEME_KEY = "debate.theme";
const SOUND_KEY = "debate.sound";

function readTheme(): ThemeChoice {
  const stored = localStorage.getItem(THEME_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme);
  const [systemDark, setSystemDark] = useState(prefersDark);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (choice === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", choice);
    localStorage.setItem(THEME_KEY, choice);
  }, [choice]);

  const resolved: "light" | "dark" =
    choice === "system" ? (systemDark ? "dark" : "light") : choice;

  // Cycling forward from what is on screen, so the first click always visibly
  // flips the theme rather than landing on the mode already in effect.
  const cycle = useCallback(() => {
    setChoice((current) => {
      if (current === "system") return systemDark ? "light" : "dark";
      return current === "dark" ? "light" : "system";
    });
  }, [systemDark]);

  return { choice, resolved, cycle };
}

export function useTypingSound() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(SOUND_KEY) !== "off");

  useEffect(() => {
    localStorage.setItem(SOUND_KEY, enabled ? "on" : "off");
    keyboard.setEnabled(enabled);
  }, [enabled]);

  /**
   * Browsers only allow audio to start from a user gesture, so the audio context
   * is opened on the click that starts a debate rather than on mount.
   */
  const armFromGesture = useCallback(() => {
    if (enabled) keyboard.setEnabled(true);
  }, [enabled]);

  return { enabled, toggle: () => setEnabled((on) => !on), armFromGesture };
}
