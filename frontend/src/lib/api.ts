import type {
  DietInfo, Exercise, Metrics, Plan, Profile, Settings, Streak, Today,
} from "./types";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
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
  }) => post("/api/log", body).then(j<{ ok: boolean; streak: Streak }>),

  getStreak: () => fetch("/api/streak").then(j<Streak>),
  getMetrics: () => fetch("/api/metrics").then(j<Metrics>),
  logWeight: (weight_kg: number, date?: string) =>
    post("/api/weight", { weight_kg, date }).then(j<{ ok: boolean }>),

  getDiet: () => fetch("/api/diet").then(j<DietInfo>),

  getSettings: () => fetch("/api/settings").then(j<Settings>),
  saveSettings: (s: Partial<Settings>) => post("/api/settings", s).then(j<Settings>),

  resetApp: () => post("/api/reset", {}).then(j<{ ok: boolean }>),
  getNotificationStatus: () =>
    fetch("/api/notifications/status").then(
      j<{ termux_cli: boolean; last_fired: string | null; last_error: string | null }>,
    ),
  testNotification: () =>
    post("/api/notifications/test", {}).then(
      j<{ sent: boolean; termux: boolean; error: string | null }>,
    ),
};
