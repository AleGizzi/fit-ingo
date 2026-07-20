import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { haptic } from "../lib/haptics";
import { exInstructions, exName } from "../lib/format";
import type { Exercise, PlanItem } from "../lib/types";

/** P3 — one exercise at a time with real timers.
 *
 * Timers are wall-clock based (an end timestamp, not tick accumulation), so a
 * backgrounded tab stays correct and visibility changes need no special code:
 * the next interval tick recomputes from Date.now().
 */
export function GuidedFlow({
  items,
  exercises,
  doneKeys,
  keyOf,
  onCompleteItem,
  onAllDone,
  onSwap,
}: {
  items: PlanItem[];
  exercises: Record<string, Exercise>;
  doneKeys: Set<string>;
  keyOf: (it: PlanItem) => string;
  onCompleteItem: (key: string) => void;
  onAllDone: () => void;
  onSwap: (it: PlanItem) => void;
}) {
  const { t, i18n } = useTranslation();
  const firstOpen = items.findIndex((it) => !doneKeys.has(keyOf(it)));
  const [idx, setIdx] = useState(firstOpen === -1 ? 0 : firstOpen);
  const [setNum, setSetNum] = useState(1);
  const [phase, setPhase] = useState<"work" | "rest">("work");

  const item = items[idx];
  const sets = item?.sets ?? 1;
  const isTimed = item?.duration_sec != null;

  // If the active item got ticked from List mode, hop to the next open one.
  useEffect(() => {
    if (item && doneKeys.has(keyOf(item))) {
      const next = items.findIndex((it) => !doneKeys.has(keyOf(it)));
      if (next === -1) return; // parent shows the rating sheet
      setIdx(next);
      setSetNum(1);
      setPhase("work");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doneKeys]);

  function completeSet() {
    haptic.set();
    if (setNum < sets) {
      if ((item.rest_sec ?? 0) > 0) {
        setPhase("rest");
      } else {
        setSetNum((n) => n + 1);
      }
    } else {
      completeItem();
    }
  }

  function completeItem() {
    const key = keyOf(item);
    onCompleteItem(key);
    // Find the next open item, treating the current one as done locally
    // (the doneKeys prop updates on the next render).
    const next = items.findIndex((it, i) => i !== idx && !doneKeys.has(keyOf(it)));
    if (next === -1) {
      onAllDone();
    } else {
      setIdx(next);
      setSetNum(1);
      setPhase("work");
    }
  }

  function endRest() {
    haptic.restEnd();
    setSetNum((n) => n + 1);
    setPhase("work");
  }

  if (!item) return null;
  const ex = exercises[item.exercise_id];

  return (
    <div className="gf">
      <span className="eyebrow">{t(`workout.${item.block}`)}</span>
      <div className="gf-namerow">
        <h2 className="gf-name">{exName(ex, i18n.language)}</h2>
        <button className="gf-swap" onClick={() => onSwap(item)}
          aria-label={t("workout.swapOpen")}>⇄</button>
      </div>
      {/* P9: hr chip mounts here */}
      {sets > 1 && (
        <div className="gf-sets num">
          {t("workout.setOf", { n: setNum, total: sets })}
        </div>
      )}

      {phase === "work" ? (
        isTimed ? (
          <WorkTimer
            key={`${idx}:${setNum}`}
            seconds={item.duration_sec!}
            onDone={completeSet}
          />
        ) : (
          <div className="gf-reps">
            <div className="gf-count num">{item.reps}</div>
            <div className="gf-count-lbl">{t("common.reps")}</div>
          </div>
        )
      ) : (
        <RestTimer
          key={`rest:${idx}:${setNum}`}
          seconds={item.rest_sec ?? 30}
          onDone={endRest}
          onSkip={endRest}
        />
      )}

      {phase === "work" && !isTimed && (
        <button className="gf-done-btn" onClick={completeSet}>
          ✓ {t("common.done")}
        </button>
      )}

      <p className="ex-instructions gf-instructions">
        {exInstructions(ex, i18n.language)}
      </p>
      {ex?.video_url && (
        <a className="ex-video" href={ex.video_url} target="_blank" rel="noreferrer">
          ▶ {t("workout.watch")}
        </a>
      )}
    </div>
  );
}

/** Remaining ms from a wall-clock deadline — the only timer math there is. */
export function remainingMs(endAt: number, now: number): number {
  return Math.max(0, endAt - now);
}

function useWallClockCountdown(seconds: number, onDone: () => void) {
  const [remaining, setRemaining] = useState(seconds * 1000);
  const [paused, setPaused] = useState(false);
  const endAtRef = useRef<number>(Date.now() + seconds * 1000);
  const pausedRemRef = useRef<number>(seconds * 1000);
  const doneRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => {
      const rem = remainingMs(endAtRef.current, Date.now());
      setRemaining(rem);
      if (rem <= 0 && !doneRef.current) {
        doneRef.current = true;
        clearInterval(id);
        onDoneRef.current();
      }
    }, 200);
    return () => clearInterval(id);
  }, [paused]);

  function toggle() {
    setPaused((p) => {
      if (!p) {
        pausedRemRef.current = remainingMs(endAtRef.current, Date.now());
      } else {
        endAtRef.current = Date.now() + pausedRemRef.current;
      }
      return !p;
    });
  }

  return { remaining, paused, toggle };
}

function fmt(ms: number): string {
  const s = Math.ceil(ms / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : `${s}`;
}

function WorkTimer({ seconds, onDone }: { seconds: number; onDone: () => void }) {
  const { t } = useTranslation();
  const { remaining, paused, toggle } = useWallClockCountdown(seconds, onDone);
  return (
    <div className="gf-timer gf-timer-work">
      <div className="gf-count num">{fmt(remaining)}</div>
      <div className="gf-track">
        <div
          className="gf-fill gf-fill-work"
          style={{ width: `${(remaining / (seconds * 1000)) * 100}%` }}
        />
      </div>
      <button className="gf-pause" onClick={toggle}>
        {paused ? `▶ ${t("workout.resumeTimer")}` : `⏸ ${t("workout.pause")}`}
      </button>
    </div>
  );
}

function RestTimer({ seconds, onDone, onSkip }: {
  seconds: number; onDone: () => void; onSkip: () => void;
}) {
  const { t } = useTranslation();
  const { remaining } = useWallClockCountdown(seconds, onDone);
  return (
    <div className="gf-timer gf-timer-rest">
      <div className="gf-rest-lbl">{t("workout.rest")}</div>
      <div className="gf-count num">{fmt(remaining)}</div>
      <div className="gf-track">
        <div
          className="gf-fill gf-fill-rest"
          style={{ width: `${(remaining / (seconds * 1000)) * 100}%` }}
        />
      </div>
      <button className="gf-pause" onClick={onSkip}>
        {t("workout.skipRest")} →
      </button>
    </div>
  );
}
