import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";
import type { Activity, HealthSummary, Metrics } from "../lib/types";
import "./progress.css";

export function Progress() {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [weight, setWeight] = useState("");
  const [saving, setSaving] = useState(false);
  const [health, setHealth] = useState<HealthSummary | null>(null);

  const load = () => api.getMetrics().then(setMetrics).catch(() => setMetrics(null));
  const loadHealth = () => api.getHealthSummary().then(setHealth).catch(() => setHealth(null));
  useEffect(() => { load(); loadHealth(); }, []);

  async function addWeight() {
    const w = parseFloat(weight);
    if (!w || w <= 0) return;
    setSaving(true);
    try {
      await api.logWeight(w);
      setWeight("");
      await load();
    } finally {
      setSaving(false);
    }
  }

  if (!metrics) return <p className="muted">{t("common.loading")}</p>;

  const { streak, totals } = metrics;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("app.name")}</span>
          <h1 className="page-title">{t("progress.title")}</h1>
        </div>
      </header>

      <div className="stat-grid">
        <StatTile value={streak.current} label={t("progress.streak")} accent="ember" suffix="🔥" />
        <StatTile value={streak.best} label={t("progress.best")} accent="gold" />
        <StatTile value={`${Math.round(totals.completion_rate * 100)}%`} label={t("progress.completion")} accent="mint" />
        <StatTile value={totals.workouts_completed} label={t("progress.workouts")} accent="violet" />
      </div>

      <Card>
        <div className="spread" style={{ marginBottom: 12 }}>
          <span className="eyebrow">{t("progress.weightTrend")}</span>
        </div>
        {metrics.weights.length >= 2 ? (
          <WeightChart data={metrics.weights} />
        ) : (
          <p className="muted">{t("progress.noWeight")}</p>
        )}
        <div className="weight-form">
          <input
            className="text-input"
            type="number"
            inputMode="decimal"
            placeholder={t("progress.weightKg")}
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
          />
          <Button variant="violet" onClick={addWeight} disabled={saving || !weight}>
            {t("progress.add")}
          </Button>
        </div>
      </Card>

      <Card>
        <span className="eyebrow">{t("progress.consistency")}</span>
        <ConsistencyChart logs={metrics.logs} />
      </Card>

      <HealthSection health={health} onImported={loadHealth} />
    </div>
  );
}

/** Wearable data: imported locally from .FIT files — no cloud account. */
function HealthSection({ health, onImported }: {
  health: HealthSummary | null;
  onImported: () => void;
}) {
  const { t, i18n } = useTranslation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const hasData = !!health && (health.daily.length > 0 || health.activities.length > 0);

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await api.importHealth(files);
      const parts = [
        t("health.imported", { acts: res.activities_imported, days: res.days_updated }),
        ...res.errors,
      ];
      setResult(parts.join(" · "));
      onImported();
    } catch (e) {
      setResult(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const steps = (health?.daily ?? []).filter((d) => d.steps != null).slice(-14);
  const rhr = (health?.daily ?? []).filter((d) => d.resting_hr != null).slice(-30);
  const maxSteps = Math.max(1, ...steps.map((d) => d.steps ?? 0));

  return (
    <Card className="stack">
      <div className="spread">
        <span className="eyebrow">⌚ {t("health.title")}</span>
        <Button variant="soft" onClick={() => fileRef.current?.click()} disabled={busy}>
          {busy ? t("common.loading") : t("health.import")}
        </Button>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept=".fit,.FIT"
        multiple
        hidden
        onChange={(e) => onFiles(e.target.files)}
      />
      {result && <p className="muted setting-help">{result}</p>}

      {!hasData ? (
        <p className="muted">{t("health.empty")}</p>
      ) : (
        <>
          {steps.length > 0 && (
            <div>
              <span className="health-sub">{t("health.steps")}</span>
              <div className="bars bars-steps">
                {steps.map((d) => (
                  <div className="bar-col" key={d.date} title={`${d.date}: ${d.steps}`}>
                    <div className="bar-track">
                      <div className="bar-fill bar-steps" style={{ height: `${((d.steps ?? 0) / maxSteps) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <p className="muted health-latest">
                {t("health.stepsLatest", { n: steps[steps.length - 1].steps?.toLocaleString() })}
              </p>
            </div>
          )}

          {rhr.length >= 2 && (
            <div>
              <span className="health-sub">{t("health.restingHr")}</span>
              <HrChart data={rhr.map((d) => ({ date: d.date, v: d.resting_hr! }))} />
            </div>
          )}

          {health!.activities.length > 0 && (
            <div>
              <span className="health-sub">{t("health.activities")}</span>
              <ul className="activity-list">
                {health!.activities.slice(0, 8).map((a) => (
                  <ActivityRow key={a.id} a={a} lang={i18n.language} />
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

const SPORT_ICON: Record<string, string> = {
  running: "🏃", walking: "🚶", cycling: "🚴", swimming: "🏊",
  training: "🏋️", fitness_equipment: "🏋️", hiking: "🥾", yoga: "🧘",
};

function ActivityRow({ a, lang }: { a: Activity; lang: string }) {
  const { t } = useTranslation();
  const d = new Date(a.start_ts);
  const when = d.toLocaleDateString(lang === "es" ? "es" : "en", {
    month: "short", day: "numeric",
  });
  const bits = [
    a.duration_min != null && `${Math.round(a.duration_min)} ${t("common.minutes")}`,
    a.distance_km != null && `${a.distance_km} km`,
    a.avg_hr != null && `♥ ${a.avg_hr}${a.max_hr != null ? `/${a.max_hr}` : ""}`,
    a.calories != null && `${a.calories} kcal`,
  ].filter(Boolean);
  return (
    <li className="activity-row">
      <span className="activity-icon">{SPORT_ICON[a.sport] ?? "⚡"}</span>
      <div className="activity-info">
        <span className="activity-sport">{a.sport.replace(/_/g, " ")}</span>
        <span className="activity-bits num">{bits.join(" · ")}</span>
      </div>
      <span className="activity-date">{when}</span>
    </li>
  );
}

/** Resting-HR line, ember accent (same construction as WeightChart). */
function HrChart({ data }: { data: { date: string; v: number }[] }) {
  const W = 300, H = 90, pad = 10;
  const vs = data.map((p) => p.v);
  const min = Math.min(...vs), max = Math.max(...vs);
  const span = max - min || 1;
  const x = (i: number) => pad + (i / (data.length - 1)) * (W - pad * 2);
  const y = (v: number) => pad + (1 - (v - min) / span) * (H - pad * 2);
  const path = data.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const last = data[data.length - 1];
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img"
        aria-label={`Resting heart rate, latest ${last.v} bpm`}>
        <path d={path} fill="none" stroke="var(--ember)" strokeWidth={2.5}
          strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={x(data.length - 1)} cy={y(last.v)} r={5} fill="var(--ember)" />
      </svg>
      <div className="chart-range">
        <span className="num">{min}</span>
        <span className="chart-latest chart-latest-hr num">{last.v} bpm</span>
        <span className="num">{max}</span>
      </div>
    </div>
  );
}

function StatTile({ value, label, accent, suffix }: {
  value: number | string; label: string; accent: string; suffix?: string;
}) {
  return (
    <div className={`stat-tile stat-${accent}`}>
      <div className="stat-value num">{value}{suffix && <span className="stat-suffix">{suffix}</span>}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/** Single-series line chart (violet). Baseline scaled to data range. */
function WeightChart({ data }: { data: { date: string; weight_kg: number }[] }) {
  const W = 300, H = 120, pad = 10;
  const pts = data.slice(-30);
  const ws = pts.map((p) => p.weight_kg);
  const min = Math.min(...ws), max = Math.max(...ws);
  const span = max - min || 1;
  const x = (i: number) => pad + (i / (pts.length - 1)) * (W - pad * 2);
  const y = (w: number) => pad + (1 - (w - min) / span) * (H - pad * 2);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.weight_kg).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img"
        aria-label={`Weight trend, latest ${last.weight_kg} kg`}>
        <path d={path} fill="none" stroke="var(--violet)" strokeWidth={2.5}
          strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={x(pts.length - 1)} cy={y(last.weight_kg)} r={5} fill="var(--violet)" />
      </svg>
      <div className="chart-range">
        <span className="num">{min.toFixed(1)}</span>
        <span className="chart-latest num">{last.weight_kg.toFixed(1)} kg</span>
        <span className="num">{max.toFixed(1)}</span>
      </div>
    </div>
  );
}

/** Completed workouts per ISO week for the last 12 weeks (mint bars). */
function ConsistencyChart({ logs }: { logs: Metrics["logs"] }) {
  const weeks = buildWeeks(logs, 12);
  const maxCount = Math.max(1, ...weeks.map((w) => w.count));
  return (
    <div className="bars">
      {weeks.map((w, i) => (
        <div className="bar-col" key={i} title={`${w.count}`}>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ height: `${(w.count / maxCount) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function buildWeeks(logs: Metrics["logs"], n: number) {
  const now = new Date();
  const thisMonday = new Date(now);
  thisMonday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  thisMonday.setHours(0, 0, 0, 0);
  const buckets = Array.from({ length: n }, (_, i) => {
    const start = new Date(thisMonday);
    start.setDate(thisMonday.getDate() - (n - 1 - i) * 7);
    return { start, count: 0 };
  });
  for (const log of logs) {
    if (!log.completed) continue;
    const d = new Date(log.date + "T00:00:00");
    for (let i = buckets.length - 1; i >= 0; i--) {
      if (d >= buckets[i].start) { buckets[i].count++; break; }
    }
  }
  return buckets;
}
