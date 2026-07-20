import type {
  DietInfo, Exercise, HealthSummary, HistoryEntry, Metrics, Plan, PlanItem,
  Profile, QuickKind, QuickSession, Settings, Streak, Today, WaterToday,
} from "./types";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    // Prefer the server's JSON {error} message when present.
    let msg = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.error) msg = parsed.error;
    } catch { /* not JSON, use raw text */ }
    throw new Error(msg || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

const post = (url: string, body: unknown) =>
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const api = {
  getProfile: () => fetch("/api/profile").then(j<Profile | null>),
  saveProfile: (p: Partial<Profile>) =>
    post("/api/profile", p).then(j<{ profile: Profile; plan: Plan }>),

  getExercises: () => fetch("/api/exercises").then(j<Exercise[]>),
  patchExerciseVideo: (id: string, video_url: string) =>
    fetch(`/api/exercises/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_url }),
    }).then(j<{ ok: boolean }>),

  getPlan: () => fetch("/api/plan").then(j<Plan | null>),
  swapItem: (plan_item_id: number, exclude = false) =>
    post("/api/plan/swap", { plan_item_id, exclude }).then(j<PlanItem>),
  regeneratePlan: () =>
    post("/api/plan/regenerate", {}).then(j<{ plan: Plan; progression_factor: number }>),

  getToday: () => fetch("/api/today").then(j<Today>),
  logWorkout: (body: {
    date?: string;
    completed: boolean;
    items_done: string[];
    items_total: number;
    perceived_difficulty?: number;
    duration_min?: number;
  }) => post("/api/log", body).then(
    j<{ ok: boolean; streak: Streak; freeze_earned: boolean }>,
  ),

  getQuick: (kind: QuickKind) => fetch(`/api/quick/${kind}`).then(j<QuickSession>),

  getStreak: () => fetch("/api/streak").then(j<Streak>),
  getMetrics: () => fetch("/api/metrics").then(j<Metrics>),
  getHistory: (limit = 30) =>
    fetch(`/api/history?limit=${limit}`).then(j<HistoryEntry[]>),
  logWeight: (weight_kg: number, date?: string) =>
    post("/api/weight", { weight_kg, date }).then(j<{ ok: boolean }>),

  getDiet: () => fetch("/api/diet").then(j<DietInfo>),

  getWater: () => fetch("/api/water").then(j<WaterToday>),
  logWater: (delta_ml: number) =>
    post("/api/water", { delta_ml }).then(j<WaterToday>),

  getHealthSummary: () => fetch("/api/health/summary").then(j<HealthSummary>),
  importHealth: (files: FileList | File[]) => {
    const form = new FormData();
    for (const f of Array.from(files)) form.append("files", f);
    return fetch("/api/health/import", { method: "POST", body: form }).then(
      j<{ activities_imported: number; days_updated: number; errors: string[] }>,
    );
  },

  getSettings: () => fetch("/api/settings").then(j<Settings>),
  saveSettings: (s: Partial<Settings>) => post("/api/settings", s).then(j<Settings>),

  resetApp: () => post("/api/reset", {}).then(j<{ ok: boolean }>),

  /** Backup downloads via a plain <a download> — no fetch, so the file never
   *  passes through JS memory. Restore posts the file back. */
  restoreBackup: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/restore", { method: "POST", body: form })
      .then(j<{ ok: boolean }>);
  },
  getNotificationStatus: () =>
    fetch("/api/notifications/status").then(
      j<{
        termux_cli: boolean;
        last_fired: string | null;
        last_error: string | null;
        last_tick: string | null;
      }>,
    ),
  testNotification: () =>
    post("/api/notifications/test", {}).then(
      j<{ sent: boolean; termux: boolean; error: string | null }>,
    ),
};
