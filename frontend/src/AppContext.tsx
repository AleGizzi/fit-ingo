import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { api } from "./lib/api";
import type { Exercise, Profile, Settings, Theme } from "./lib/types";

interface AppState {
  ready: boolean;
  profile: Profile | null;
  settings: Settings | null;
  exercises: Record<string, Exercise>;
  reload: () => Promise<void>;
  setSettings: (s: Settings) => void;
  setProfile: (p: Profile | null) => void;
}

const Ctx = createContext<AppState | null>(null);

function applyTheme(theme: Theme) {
  const resolved =
    theme === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
  document.documentElement.setAttribute("data-theme", resolved);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", resolved === "dark" ? "#14121C" : "#FF5A1F");
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation();
  const [ready, setReady] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettingsState] = useState<Settings | null>(null);
  const [exercises, setExercises] = useState<Record<string, Exercise>>({});

  const reload = useCallback(async () => {
    const [p, s, ex] = await Promise.all([
      api.getProfile().catch(() => null),
      api.getSettings().catch(() => null),
      api.getExercises().catch(() => [] as Exercise[]),
    ]);
    setProfile(p);
    if (s) {
      setSettingsState(s);
      i18n.changeLanguage(s.language);
      applyTheme(s.theme);
    }
    setExercises(Object.fromEntries(ex.map((e) => [e.id, e])));
    setReady(true);
  }, [i18n]);

  useEffect(() => {
    reload();
  }, [reload]);

  // React to OS theme changes when in "system" mode.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => settings?.theme === "system" && applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [settings?.theme]);

  const setSettings = useCallback(
    (s: Settings) => {
      setSettingsState(s);
      i18n.changeLanguage(s.language);
      applyTheme(s.theme);
    },
    [i18n],
  );

  const value = useMemo(
    () => ({ ready, profile, settings, exercises, reload, setSettings, setProfile }),
    [ready, profile, settings, exercises, reload, setSettings],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp must be used within AppProvider");
  return c;
}
