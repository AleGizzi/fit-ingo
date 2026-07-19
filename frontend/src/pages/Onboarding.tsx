import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button, OptionTile, Segmented, Stepper } from "../components/ui";
import type { Equipment, Goal, Impact, Lang, Level, Profile } from "../lib/types";
import "./onboarding.css";

const GOALS: Goal[] = ["lose", "maintain", "gain_muscle", "general"];
const GOAL_ICON: Record<Goal, string> = { lose: "🔥", maintain: "⚖️", gain_muscle: "💪", general: "🌱" };
const LEVELS: Level[] = ["beginner", "intermediate", "advanced"];
const IMPACTS: Impact[] = ["none", "low", "normal"];
const IMPACT_ICON: Record<Impact, string> = { none: "🪶", low: "👣", normal: "⚡" };
const EQUIP: Equipment[] = ["none", "bands", "dumbbells"];
const EQUIP_ICON: Record<Equipment, string> = { none: "🧍", bands: "🎗️", dumbbells: "🏋️" };
const LIMITS = ["knee", "back", "shoulder", "wrist"];

const TOTAL_STEPS = 7;

export function Onboarding() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const { reload, setProfile, settings, setSettings } = useApp();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [p, setP] = useState<Profile>({
    name: "",
    age: 30,
    sex: "male",
    height_cm: 170,
    weight_kg: 75,
    goal: "maintain",
    level: "beginner",
    impact: "low",
    equipment: "none",
    days_per_week: 3,
    session_minutes: 30,
    limitations: [],
    diet_pref: "any",
  });

  const set = (patch: Partial<Profile>) => setP((prev) => ({ ...prev, ...patch }));
  const toggleLimit = (l: string) =>
    set({
      limitations: p.limitations.includes(l)
        ? p.limitations.filter((x) => x !== l)
        : [...p.limitations, l],
    });

  const next = () => setStep((s) => Math.min(TOTAL_STEPS, s + 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  // Onboarding is the only way into the app, so a silent failure here strands
  // the user on this screen forever — always surface what went wrong.
  async function submit() {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await api.saveProfile(p);
      await reload().catch(() => { /* the POST already succeeded */ });
      // Trust the profile the server just echoed back, applied *after* reload
      // so it wins: reload's GET /api/profile is cached NetworkFirst and can
      // still answer with the pre-onboarding null, which would bounce us
      // straight back to this screen.
      setProfile(res.profile);
      nav("/today", { replace: true });
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  function pickLang(v: Lang) {
    i18n.changeLanguage(v);
    if (!settings) return; // nothing to persist to yet; i18n still switches
    const merged = { ...settings, language: v };
    setSettings(merged);
    api.saveSettings(merged).then(setSettings).catch(() => { /* stays local */ });
  }

  const lang: Lang = i18n.language.startsWith("es") ? "es" : "en";

  // Step 0 is the welcome screen; steps 1..7 are questions.
  const progress = step === 0 ? 0 : (step / TOTAL_STEPS) * 100;

  return (
    <div className="onb">
      {step > 0 && (
        <div className="onb-top">
          <button className="onb-backbtn" onClick={back} aria-label={t("common.back")}>‹</button>
          <div className="onb-bar"><div className="onb-bar-fill" style={{ width: `${progress}%` }} /></div>
        </div>
      )}

      {step === 0 && (
        <div className="onb-welcome">
          <div className="onb-flame">🔥</div>
          <h1 className="onb-welcome-title">{t("onboarding.welcome")}</h1>
          <p className="onb-welcome-intro">{t("onboarding.intro")}</p>
          <div className="onb-lang">
            <Segmented<Lang>
              value={lang}
              onChange={pickLang}
              options={[
                { value: "en", label: "English" },
                { value: "es", label: "Español" },
              ]}
            />
          </div>
          <Button block onClick={next}>{t("onboarding.letsgo")}</Button>
        </div>
      )}

      {step === 1 && (
        <Step title={t("onboarding.name")} n={1}>
          <input
            className="text-input"
            placeholder={t("onboarding.namePlaceholder")}
            value={p.name}
            onChange={(e) => set({ name: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && next()}
            enterKeyHint="next"
            autoFocus
          />
        </Step>
      )}

      {step === 2 && (
        <Step title={t("onboarding.about")} n={2}>
          <div className="stack">
            <div>
              <label className="field-label">{t("onboarding.sex")}</label>
              <Segmented
                value={p.sex}
                onChange={(v) => set({ sex: v })}
                options={[
                  { value: "male", label: t("onboarding.sexMale") },
                  { value: "female", label: t("onboarding.sexFemale") },
                  { value: "other", label: t("onboarding.sexOther") },
                ]}
              />
            </div>
            <div className="spread">
              <label className="field-label">{t("onboarding.age")}</label>
              <Stepper value={p.age} min={12} max={99} onChange={(v) => set({ age: v })} />
            </div>
            <div className="spread">
              <label className="field-label">{t("onboarding.height")}</label>
              <Stepper value={p.height_cm} min={120} max={220} onChange={(v) => set({ height_cm: v })} />
            </div>
            <div className="spread">
              <label className="field-label">{t("onboarding.weight")}</label>
              <Stepper value={p.weight_kg} min={35} max={200} onChange={(v) => set({ weight_kg: v })} />
            </div>
          </div>
        </Step>
      )}

      {step === 3 && (
        <Step title={t("onboarding.goalTitle")} n={3}>
          <div className="stack">
            {GOALS.map((g) => (
              <OptionTile
                key={g}
                selected={p.goal === g}
                icon={GOAL_ICON[g]}
                title={t(`goal.${g}`)}
                desc={t(`goal.${g}_d`)}
                onClick={() => set({ goal: g })}
              />
            ))}
          </div>
        </Step>
      )}

      {step === 4 && (
        <Step title={t("onboarding.levelTitle")} n={4}>
          <div className="stack">
            {LEVELS.map((l) => (
              <OptionTile
                key={l}
                selected={p.level === l}
                title={t(`level.${l}`)}
                desc={t(`level.${l}_d`)}
                onClick={() => set({ level: l })}
              />
            ))}
          </div>
        </Step>
      )}

      {step === 5 && (
        <Step title={t("onboarding.impactTitle")} n={5} help={t("onboarding.impactHelp")}>
          <div className="stack">
            {IMPACTS.map((im) => (
              <OptionTile
                key={im}
                selected={p.impact === im}
                icon={IMPACT_ICON[im]}
                title={t(`impact.${im}`)}
                desc={t(`impact.${im}_d`)}
                onClick={() => set({ impact: im })}
              />
            ))}
          </div>
        </Step>
      )}

      {step === 6 && (
        <Step title={t("onboarding.equipmentTitle")} n={6}>
          <div className="stack">
            {EQUIP.map((eq) => (
              <OptionTile
                key={eq}
                selected={p.equipment === eq}
                icon={EQUIP_ICON[eq]}
                title={t(`equipment.${eq}`)}
                desc={t(`equipment.${eq}_d`)}
                onClick={() => set({ equipment: eq })}
              />
            ))}
          </div>
        </Step>
      )}

      {step === 7 && (
        <Step title={t("onboarding.scheduleTitle")} n={7}>
          <div className="stack">
            <div className="spread">
              <label className="field-label">{t("onboarding.daysPerWeek")}</label>
              <Stepper value={p.days_per_week} min={1} max={6} onChange={(v) => set({ days_per_week: v })} />
            </div>
            <div className="spread">
              <label className="field-label">{t("onboarding.sessionMinutes")}</label>
              <Stepper value={p.session_minutes} min={10} max={90} step={5} onChange={(v) => set({ session_minutes: v })} />
            </div>

            <div>
              <label className="field-label">{t("onboarding.limitationsTitle")}</label>
              <p className="muted" style={{ marginBottom: 10 }}>{t("onboarding.limitationsHelp")}</p>
              <div className="chip-row">
                {LIMITS.map((l) => (
                  <button
                    key={l}
                    className={`chip ${p.limitations.includes(l) ? "chip-on" : ""}`}
                    onClick={() => toggleLimit(l)}
                  >
                    {t(`limitations.${l}`)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="field-label">{t("onboarding.dietTitle")}</label>
              <Segmented
                value={p.diet_pref ?? "any"}
                onChange={(v) => set({ diet_pref: v })}
                options={[
                  { value: "any", label: t("diet.any") },
                  { value: "vegetarian", label: t("diet.vegetarian") },
                ]}
              />
            </div>
          </div>
        </Step>
      )}

      {step > 0 && (
        <div className="onb-actions">
          {saveError && (
            <p className="onb-error">
              ⚠️ {t("onboarding.saveError")}
              <br />
              <span className="onb-error-detail">{saveError}</span>
            </p>
          )}
          {step < TOTAL_STEPS ? (
            <Button block onClick={next}>{t("common.next")}</Button>
          ) : (
            <Button block onClick={submit} disabled={saving}>
              {saving
                ? t("onboarding.building")
                : saveError
                  ? t("workout.retry")
                  : t("onboarding.buildPlan")}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function Step({
  title, n, help, children,
}: {
  title: string; n: number; help?: string; children: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="onb-step">
      <span className="eyebrow">{t("onboarding.step", { n, total: TOTAL_STEPS })}</span>
      <h2 className="onb-q">{title}</h2>
      {help && <p className="muted onb-help">{help}</p>}
      <div className="onb-body">{children}</div>
    </div>
  );
}
