import type { Exercise, PlanItem } from "./types";

export function exName(ex: Exercise | undefined, lang: string): string {
  if (!ex) return "";
  return lang === "es" ? ex.name_es : ex.name_en;
}

export function exInstructions(ex: Exercise | undefined, lang: string): string {
  if (!ex) return "";
  return lang === "es" ? ex.instructions_es : ex.instructions_en;
}

/** A short human label for an item's dose, e.g. "3 × 12" or "3 × 45s". */
export function itemDose(item: PlanItem): string {
  const sets = item.sets ?? 1;
  if (item.reps != null) return `${sets} × ${item.reps}`;
  if (item.duration_sec != null) return `${sets} × ${item.duration_sec}s`;
  return `${sets}`;
}

/** Rough estimate of session length in minutes from its items. */
export function estimateMinutes(items: PlanItem[]): number {
  let sec = 0;
  for (const it of items) {
    const sets = it.sets ?? 1;
    const work = it.duration_sec != null ? it.duration_sec : (it.reps ?? 10) * 3;
    sec += sets * work + sets * (it.rest_sec ?? 20);
  }
  return Math.max(5, Math.round(sec / 60));
}

/** Localized weekday short names, Monday-first (weekday 0 = Mon). */
export function weekdayShort(lang: string): string[] {
  return lang === "es"
    ? ["L", "M", "X", "J", "V", "S", "D"]
    : ["M", "T", "W", "T", "F", "S", "S"];
}

export function todayWeekday(): number {
  // JS: 0=Sun..6=Sat -> our 0=Mon..6=Sun
  return (new Date().getDay() + 6) % 7;
}
