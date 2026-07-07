import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";
import type { Metrics } from "../lib/types";
import "./progress.css";

export function Progress() {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [weight, setWeight] = useState("");
  const [saving, setSaving] = useState(false);

  const load = () => api.getMetrics().then(setMetrics).catch(() => setMetrics(null));
  useEffect(() => { load(); }, []);

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
