import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";
import { Flame } from "../components/Flame";
import { WeekRing } from "../components/WeekRing";
import type { DayState } from "../components/WeekRing";
import { estimateMinutes, exName, todayWeekday } from "../lib/format";
import type { Metrics, Plan, Streak, Today as TodayT, WaterToday } from "../lib/types";
import "./today.css";

export function Today() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const { profile, exercises } = useApp();
  const [today, setToday] = useState<TodayT | null>(null);
  const [streak, setStreak] = useState<Streak | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [water, setWater] = useState<WaterToday | null>(null);

  useEffect(() => {
    Promise.all([
      api.getToday().catch(() => null),
      api.getStreak().catch(() => null),
      api.getPlan().catch(() => null),
      api.getMetrics().catch(() => null),
      api.getWater().catch(() => null),
    ]).then(([td, st, pl, mt, wt]) => {
      setToday(td);
      setStreak(st);
      setPlan(pl);
      setMetrics(mt);
      setWater(wt);
    });
  }, []);

  async function drink(delta: number) {
    if (!water) return;
    // Optimistic; the response corrects if the server clamps.
    setWater({ ...water, ml: Math.max(0, water.ml + delta) });
    try {
      setWater(await api.logWater(delta));
    } catch {
      setWater(await api.getWater().catch(() => water));
    }
  }

  if (!today || !streak) {
    return <p className="muted">{t("common.loading")}</p>;
  }

  const day = today.day;
  const isRest = !day || day.is_rest;
  const done = !!today.log?.completed;
  const items = day?.items ?? [];
  const est = estimateMinutes(items);
  const weekStates = buildWeekStates(plan, metrics, done);

  const greeting = profile?.name ? `${hello(i18n.language)}, ${profile.name}` : hello(i18n.language);

  return (
    <div className="today">
      <header className="today-head">
        <div>
          <span className="eyebrow">{greeting}</span>
          <h1 className="page-title">{t("app.name")}</h1>
        </div>
      </header>

      <Card className="streak-card">
        <Flame count={streak.current} dim={streak.current === 0 || streak.at_risk} />
        <div className="streak-meta">
          <div className="streak-count num">{streak.current}</div>
          <div className="streak-label">{t("today.streak")}</div>
          <div className="streak-best">{t("today.streakBest", { n: streak.best })}</div>
        </div>
      </Card>

      <div className="week-block">
        <span className="eyebrow">{t("today.week")}</span>
        <WeekRing states={weekStates} lang={i18n.language} />
      </div>

      {streak.at_risk && !done && (
        <div className="risk-banner">⚠️ {t("today.atRisk")}</div>
      )}

      {done ? (
        <Card className="today-state">
          <div className="today-state-icon">🎉</div>
          <h2 className="today-state-title">{t("today.completed")}</h2>
          <p className="muted">{t("today.completedBody")}</p>
          <Button variant="soft" onClick={() => nav("/workout")}>
            {t("today.viewWorkout")}
          </Button>
        </Card>
      ) : isRest ? (
        <Card className="today-state">
          <div className="today-state-icon">🌙</div>
          <h2 className="today-state-title">{t("today.restTitle")}</h2>
          <p className="muted">{t("today.restBody")}</p>
        </Card>
      ) : (
        <Card className="workout-card">
          <div className="spread">
            <div>
              <span className="eyebrow">{t("today.todaysWorkout")}</span>
              <h2 className="workout-focus">{focusLabel(day!.focus)}</h2>
            </div>
            <span className="workout-est">{t("today.estMinutes", { n: est })}</span>
          </div>
          <ul className="preview-list">
            {items.filter((i) => i.block === "main").slice(0, 4).map((it) => (
              <li key={it.id}>{exName(exercises[it.exercise_id], i18n.language)}</li>
            ))}
            {items.filter((i) => i.block === "main").length > 4 && (
              <li className="preview-more">
                +{items.filter((i) => i.block === "main").length - 4}
              </li>
            )}
          </ul>
          <Button block onClick={() => nav("/workout")}>
            {today.log ? t("today.resume") : t("today.startWorkout")}
          </Button>
        </Card>
      )}

      {water && (
        <Card className="water-card">
          <div className="spread">
            <div>
              <span className="eyebrow">💧 {t("water.title")}</span>
              <div className="water-amount num">
                {(water.ml / 1000).toFixed(water.ml % 1000 ? 2 : 1)} L
                <span className="water-goal"> / {(water.goal_ml / 1000).toFixed(1)} L</span>
              </div>
            </div>
            {water.ml >= water.goal_ml && <span className="water-done">✓ {t("water.goalReached")}</span>}
          </div>
          <div className="water-track">
            <div
              className="water-fill"
              style={{ width: `${Math.min(100, (water.ml / water.goal_ml) * 100)}%` }}
            />
          </div>
          <div className="water-actions">
            <button className="water-btn" onClick={() => drink(250)}>🥛 +250</button>
            <button className="water-btn" onClick={() => drink(500)}>🍶 +500</button>
            <button className="water-btn water-undo" onClick={() => drink(-250)} disabled={water.ml === 0}>
              {t("workout.undo")}
            </button>
          </div>
        </Card>
      )}

      {/* Bonus mini-sessions: always available, never touch the streak. */}
      <div className="bonus-block">
        <span className="eyebrow">{t("quick.bonus")}</span>
        <div className="bonus-row">
          <BonusTile icon="⚡" label={t("quick.quickTitle")} sub={t("quick.quickSub")} onClick={() => nav("/quick/quick")} />
          <BonusTile icon="🪑" label={t("quick.deskTitle")} sub={t("quick.deskSub")} onClick={() => nav("/quick/desk")} />
          <BonusTile icon="🧘" label={t("quick.wellnessTitle")} sub={t("quick.wellnessSub")} onClick={() => nav("/quick/wellness")} />
        </div>
      </div>
    </div>
  );
}

function BonusTile({ icon, label, sub, onClick }: {
  icon: string; label: string; sub: string; onClick: () => void;
}) {
  return (
    <button className="bonus-tile" onClick={onClick}>
      <span className="bonus-icon">{icon}</span>
      <span className="bonus-label">{label}</span>
      <span className="bonus-sub">{sub}</span>
    </button>
  );
}

function hello(lang: string) {
  const h = new Date().getHours();
  if (lang === "es") return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
  return h < 12 ? "Good morning" : h < 19 ? "Good afternoon" : "Good evening";
}

function focusLabel(focus: string) {
  return focus
    .split("+")
    .map((s) => s.replace(/_/g, " "))
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" · ");
}

/** Build the 7-day (Mon..Sun) week strip from plan schedule + this week's logs. */
function buildWeekStates(plan: Plan | null, metrics: Metrics | null, todayDone: boolean): DayState[] {
  const twd = todayWeekday();
  const training = new Set(
    (plan?.days ?? []).filter((d) => !d.is_rest).map((d) => d.weekday),
  );
  // Map this week's completed dates to weekday index.
  const doneWeekdays = new Set<number>();
  if (metrics) {
    const now = new Date();
    const monday = new Date(now);
    monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
    monday.setHours(0, 0, 0, 0);
    for (const log of metrics.logs) {
      if (!log.completed) continue;
      const d = new Date(log.date + "T00:00:00");
      if (d >= monday) doneWeekdays.add((d.getDay() + 6) % 7);
    }
  }
  if (todayDone) doneWeekdays.add(twd);

  return Array.from({ length: 7 }, (_, wd): DayState => {
    if (doneWeekdays.has(wd)) return "done";
    if (wd === twd) return "today";
    if (!training.has(wd)) return "rest";
    if (wd < twd) return "missed";
    return "future";
  });
}
