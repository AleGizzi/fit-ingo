export type Goal = "lose" | "maintain" | "gain_muscle" | "general";
export type Level = "beginner" | "intermediate" | "advanced";
export type Impact = "none" | "low" | "normal";
export type Equipment = "none" | "bands" | "dumbbells";
export type DietPref = "any" | "vegetarian";
export type Lang = "en" | "es";
export type Theme = "light" | "dark" | "system";

export interface Profile {
  name?: string;
  age: number;
  sex: "male" | "female" | "other";
  height_cm: number;
  weight_kg: number;
  goal: Goal;
  level: Level;
  impact: Impact;
  equipment: Equipment;
  days_per_week: number;
  session_minutes: number;
  limitations: string[];
  diet_pref?: DietPref;
}

export interface Exercise {
  id: string;
  name_en: string;
  name_es: string;
  instructions_en: string;
  instructions_es: string;
  video_url: string;
  muscle_groups: string[];
  type: "strength" | "cardio" | "mobility" | "stretch" | "balance";
  impact: string;
  difficulty: number;
  equipment: string;
  contraindications: string[];
}

export interface PlanItem {
  id: number;
  exercise_id: string;
  block: "warmup" | "main" | "cooldown";
  sets: number | null;
  reps: number | null;
  duration_sec: number | null;
  rest_sec: number | null;
  position: number;
}

export interface PlanDay {
  weekday: number;
  is_rest: boolean;
  focus: string;
  items: PlanItem[];
}

export interface Plan {
  id: number;
  week: number;
  meta: Record<string, unknown>;
  days: PlanDay[];
}

export interface WorkoutLog {
  date: string;
  completed: number;
  items_done: string;
  items_total: number;
  perceived_difficulty: number | null;
  duration_min: number | null;
}

export interface Today {
  date: string;
  weekday: number;
  day: PlanDay | null;
  log: WorkoutLog | null;
}

export interface Streak {
  current: number;
  best: number;
  at_risk: boolean;
}

export interface Settings {
  language: Lang;
  theme: Theme;
  reminder_enabled: boolean;
  reminder_times: string[];
  nag_enabled: boolean;
  nag_time: string;
}

export interface DietInfo {
  targets: {
    bmr: number;
    tdee: number;
    kcal: number;
    protein_g: number;
    fat_g: number;
    carb_g: number;
    water_ml: number;
  };
  suggestions: {
    target_kcal: number;
    meals: Record<string, { id: string; slot: string; name_en: string; name_es: string; kcal: number; protein_g: number; tags: string[] }>;
    total_kcal: number;
    total_protein_g: number;
    note_en: string;
    note_es: string;
  };
}

export interface Metrics {
  weights: { date: string; weight_kg: number }[];
  logs: {
    date: string;
    completed: number;
    items_total: number | null;
    perceived_difficulty: number | null;
    duration_min: number | null;
  }[];
  streak: Streak;
  totals: {
    workouts_completed: number;
    workouts_logged: number;
    completion_rate: number;
  };
}
