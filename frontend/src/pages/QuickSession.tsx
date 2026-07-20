import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button } from "../components/ui";
import { exInstructions, exName, itemDose } from "../lib/format";
import { haptic } from "../lib/haptics";
import type { QuickKind, QuickSession as QuickSessionT } from "../lib/types";
import "./workout.css";

const KIND_META: Record<QuickKind, { icon: string; title: string }> = {
  quick: { icon: "⚡", title: "quick.quickTitle" },
  desk: { icon: "🪑", title: "quick.deskTitle" },
  wellness: { icon: "🧘", title: "quick.wellnessTitle" },
};

/** A bonus mini-session: same checklist UI as Workout, but nothing is
 * persisted — no log, no streak, no rating. Finish, feel good, go back. */
export function QuickSession() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const { kind: kindParam } = useParams();
  const { exercises } = useApp();
  const [session, setSession] = useState<QuickSessionT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Set<number>>(new Set());
  const [finished, setFinished] = useState(false);

  const kind = (kindParam ?? "") as QuickKind;
  const meta = KIND_META[kind];

  useEffect(() => {
    if (!meta) return;
    api.getQuick(kind)
      .then(setSession)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [kind, meta]);

  if (!meta) {
    nav("/today", { replace: true });
    return null;
  }
  if (error) return <p className="muted">⚠️ {error}</p>;
  if (!session) return <p className="muted">{t("common.loading")}</p>;

  const total = session.items.length;
  const doneCount = done.size;

  function toggle(pos: number) {
    haptic.tick();
    setDone((prev) => {
      const next = new Set(prev);
      next.has(pos) ? next.delete(pos) : next.add(pos);
      return next;
    });
  }

  function finish() {
    haptic.finish();
    setFinished(true);
    setTimeout(() => nav(-1), 1400);
  }

  return (
    <div className="wk">
      <header className="wk-top">
        <button className="wk-close" onClick={() => nav(-1)} aria-label={t("common.close")}>✕</button>
        <div className="wk-progress">
          <div className="wk-progress-fill" style={{ width: `${total ? (doneCount / total) * 100 : 0}%` }} />
        </div>
        <span className="wk-count num">{doneCount}/{total}</span>
      </header>

      <div className="wk-list">
        <section className="wk-section">
          <span className="eyebrow">
            {meta.icon} {t(meta.title)} · ~{session.minutes} {t("common.minutes")}
          </span>
          {session.items.map((it) => {
            const ex = exercises[it.exercise_id];
            const isDone = done.has(it.position);
            return (
              <div key={it.position} className={`ex-card ${isDone ? "ex-done" : ""}`}>
                <div className="ex-main">
                  <div className="ex-info">
                    <h3 className="ex-name">{exName(ex, i18n.language)}</h3>
                    <span className="ex-dose num">{itemDose(it)}</span>
                  </div>
                  <button
                    className={`ex-check ${isDone ? "ex-check-on" : ""}`}
                    onClick={() => toggle(it.position)}
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
      </div>

      <div className="wk-footer">
        <Button block onClick={finish}>
          {doneCount >= total ? t("common.finish") : t("workout.finishEarly")}
        </Button>
      </div>

      {finished && (
        <div className="celebrate">
          <div className="celebrate-flame">{meta.icon}</div>
          <div className="celebrate-lbl">{t("quick.doneBody")}</div>
        </div>
      )}
    </div>
  );
}
