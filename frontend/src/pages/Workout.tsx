import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button } from "../components/ui";
import { exInstructions, exName, itemDose } from "../lib/format";
import type { PlanItem, Streak, Today } from "../lib/types";
import "./workout.css";

const BLOCK_ORDER = ["warmup", "main", "cooldown"] as const;

export function Workout() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const { exercises } = useApp();
  const [today, setToday] = useState<Today | null>(null);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const [showRating, setShowRating] = useState(false);
  const [savedStreak, setSavedStreak] = useState<Streak | null>(null);

  useEffect(() => {
    api.getToday().then((td) => {
      setToday(td);
      if (td.log?.items_done) {
        try {
          setDoneIds(new Set(JSON.parse(td.log.items_done)));
        } catch { /* ignore */ }
      }
    });
  }, []);

  const items = useMemo(() => today?.day?.items ?? [], [today]);
  const total = items.length;
  const doneCount = items.filter((i) => doneIds.has(itemKey(i))).length;
  const isReviewing = !!today?.log?.completed;

  if (!today) return <p className="muted">{t("common.loading")}</p>;
  if (!today.day || today.day.is_rest) {
    nav("/today", { replace: true });
    return null;
  }

  function toggle(item: PlanItem) {
    if (isReviewing) return;
    const key = itemKey(item);
    setDoneIds((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  async function finish(perceived?: number) {
    const completed = doneCount >= Math.ceil(total * 0.6); // 60%+ counts as done
    const res = await api.logWorkout({
      completed,
      items_done: Array.from(doneIds),
      items_total: total,
      perceived_difficulty: perceived,
      duration_min: undefined,
    });
    setSavedStreak(res.streak);
    // Brief celebration, then back to Today.
    setTimeout(() => nav("/today", { replace: true }), completed ? 1400 : 300);
  }

  const grouped = BLOCK_ORDER.map((b) => ({
    block: b,
    items: items.filter((i) => i.block === b),
  })).filter((g) => g.items.length);

  return (
    <div className="wk">
      <header className="wk-top">
        <button className="wk-close" onClick={() => nav("/today")} aria-label={t("common.close")}>✕</button>
        <div className="wk-progress">
          <div className="wk-progress-fill" style={{ width: `${total ? (doneCount / total) * 100 : 0}%` }} />
        </div>
        <span className="wk-count num">{doneCount}/{total}</span>
      </header>

      {isReviewing && <div className="wk-reviewing-badge">{t("workout.reviewing")}</div>}

      <div className="wk-list">
        {grouped.map((g) => (
          <section key={g.block} className="wk-section">
            <span className="eyebrow">{t(`workout.${g.block}`)}</span>
            {g.items.map((it) => {
              const ex = exercises[it.exercise_id];
              const isDone = doneIds.has(itemKey(it));
              return (
                <div key={it.id} className={`ex-card ${isDone ? "ex-done" : ""}`}>
                  <div className="ex-main">
                    <div className="ex-info">
                      <h3 className="ex-name">{exName(ex, i18n.language)}</h3>
                      <span className="ex-dose num">{itemDose(it)}</span>
                    </div>
                    <button
                      className={`ex-check ${isDone ? "ex-check-on" : ""}`}
                      onClick={() => toggle(it)}
                      disabled={isReviewing}
                      aria-label={isDone ? t("workout.undo") : t("workout.markDone")}
                    >
                      {isDone ? "✓" : ""}
                    </button>
                  </div>
                  <p className="ex-instructions">{exInstructions(ex, i18n.language)}</p>
                  {ex?.video_url && (
                    <a className="ex-video" href={ex.video_url} target="_blank" rel="noreferrer">
                      ▶ {t("workout.watch")}
                    </a>
                  )}
                </div>
              );
            })}
          </section>
        ))}
      </div>

      <div className="wk-footer">
        {isReviewing ? (
          <Button block variant="soft" onClick={() => nav("/today")}>
            {t("common.back")}
          </Button>
        ) : (
          <Button block onClick={() => setShowRating(true)}>
            {doneCount >= total ? t("common.finish") : t("workout.finishEarly")}
          </Button>
        )}
      </div>

      {!isReviewing && showRating && !savedStreak && (
        <div className="rating-sheet">
          <div className="rating-card">
            <h3 className="rating-title">{t("workout.howHard")}</h3>
            <div className="rating-scale">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} className="rating-dot" onClick={() => finish(n)}>
                  <span className="rating-emoji">{["😄", "🙂", "😐", "😓", "🥵"][n - 1]}</span>
                  <span className="rating-lbl">
                    {t(["workout.veryEasy", "workout.easy", "workout.okay", "workout.hard", "workout.veryHard"][n - 1])}
                  </span>
                </button>
              ))}
            </div>
            <button className="rating-skip" onClick={() => finish(undefined)}>{t("common.skip")}</button>
          </div>
        </div>
      )}

      {savedStreak && (
        <div className="celebrate">
          <div className="celebrate-flame">🔥</div>
          <div className="celebrate-num num">{savedStreak.current}</div>
          <div className="celebrate-lbl">{t("today.streak")}</div>
        </div>
      )}
    </div>
  );
}

// Warm-up/cool-down exercises can repeat across blocks; key by id+block+position.
function itemKey(it: PlanItem): string {
  return `${it.exercise_id}:${it.block}:${it.position}`;
}
