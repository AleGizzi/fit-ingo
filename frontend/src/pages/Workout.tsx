import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button, Segmented } from "../components/ui";
import { exInstructions, exName, itemDose } from "../lib/format";
import { haptic } from "../lib/haptics";
import { GuidedFlow } from "./GuidedFlow";
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
  const [freezeEarned, setFreezeEarned] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [view, setView] = useState<"guided" | "list">("guided");
  // Set once the user changes something, so autosave doesn't re-post on load.
  const dirtyRef = useRef(false);

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

  // Autosave partial progress (best-effort) so leaving mid-workout never loses
  // your checkmarks. Kept as completed=false; finishing sets the real state.
  // NOTE: must stay ABOVE the early returns — hooks after a conditional
  // return change the hook count between renders (React #310).
  useEffect(() => {
    if (isReviewing || !dirtyRef.current) return;
    const id = setTimeout(() => {
      api
        .logWorkout({
          completed: false,
          items_done: Array.from(doneIds),
          items_total: total,
        })
        .catch(() => { /* best-effort; the explicit Finish save reports errors */ });
    }, 600);
    return () => clearTimeout(id);
  }, [doneIds, isReviewing, total]);

  if (!today) return <p className="muted">{t("common.loading")}</p>;
  if (!today.day || today.day.is_rest) {
    nav("/today", { replace: true });
    return null;
  }

  function toggle(item: PlanItem) {
    if (isReviewing) return;
    dirtyRef.current = true;
    haptic.tick();
    const key = itemKey(item);
    setDoneIds((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  // Guided mode completes whole items (never un-checks).
  function completeKey(key: string) {
    dirtyRef.current = true;
    setDoneIds((prev) => new Set(prev).add(key));
  }

  async function finish(perceived?: number) {
    const completed = doneCount >= Math.ceil(total * 0.6); // 60%+ counts as done
    setSaving(true);
    setSaveError(null);
    try {
      const res = await api.logWorkout({
        completed,
        items_done: Array.from(doneIds),
        items_total: total,
        perceived_difficulty: perceived,
        duration_min: undefined,
      });
      setSavedStreak(res.streak);
      setFreezeEarned(res.freeze_earned);
      if (completed) haptic.finish();
      // Brief celebration, then back to Today (longer when a freeze drops).
      setTimeout(() => nav("/today", { replace: true }),
        completed ? (res.freeze_earned ? 2200 : 1400) : 300);
    } catch (e) {
      // Surface the failure instead of silently doing nothing.
      setSaveError(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  const grouped = BLOCK_ORDER.map((b) => ({
    block: b,
    items: items.filter((i) => i.block === b),
  })).filter((g) => g.items.length);
  const flatItems = grouped.flatMap((g) => g.items);
  const showGuided = view === "guided" && !isReviewing && !showRating && !savedStreak;

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

      {!isReviewing && (
        <div className="wk-viewswitch">
          <Segmented<"guided" | "list">
            value={view}
            onChange={setView}
            options={[
              { value: "guided", label: t("workout.guidedView") },
              { value: "list", label: t("workout.listView") },
            ]}
          />
        </div>
      )}

      {showGuided && (
        <GuidedFlow
          items={flatItems}
          exercises={exercises}
          doneKeys={doneIds}
          keyOf={itemKey}
          onCompleteItem={completeKey}
          onAllDone={() => setShowRating(true)}
        />
      )}

      {!showGuided && (
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
      )}

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
                <button
                  key={n}
                  className="rating-dot"
                  disabled={saving}
                  onClick={() => finish(n)}
                >
                  <span className="rating-emoji">{["😄", "🙂", "😐", "😓", "🥵"][n - 1]}</span>
                  <span className="rating-lbl">
                    {t(["workout.veryEasy", "workout.easy", "workout.okay", "workout.hard", "workout.veryHard"][n - 1])}
                  </span>
                </button>
              ))}
            </div>
            {saveError && (
              <p className="rating-error">⚠️ {t("workout.saveError")}<br /><span className="rating-error-detail">{saveError}</span></p>
            )}
            <button className="rating-skip" disabled={saving} onClick={() => finish(undefined)}>
              {saving ? t("common.loading") : saveError ? t("workout.retry") : t("common.skip")}
            </button>
          </div>
        </div>
      )}

      {savedStreak && (
        <div className="celebrate">
          <div className="celebrate-flame">🔥</div>
          <div className="celebrate-num num">{savedStreak.current}</div>
          <div className="celebrate-lbl">{t("today.streak")}</div>
          {freezeEarned && (
            <div className="celebrate-freeze">🧊 {t("streak.earned")}</div>
          )}
        </div>
      )}
    </div>
  );
}

// Warm-up/cool-down exercises can repeat across blocks; key by id+block+position.
function itemKey(it: PlanItem): string {
  return `${it.exercise_id}:${it.block}:${it.position}`;
}
