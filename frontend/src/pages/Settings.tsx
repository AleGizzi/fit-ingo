import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button, Card, Segmented } from "../components/ui";
import type { Lang, Settings as SettingsT, Theme } from "../lib/types";
import "./settings.css";

export function Settings() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { settings, setSettings, reload } = useApp();
  const [busy, setBusy] = useState(false);

  if (!settings) return <p className="muted">{t("common.loading")}</p>;

  async function patch(next: Partial<SettingsT>) {
    const merged = { ...settings!, ...next };
    setSettings(merged); // optimistic (updates language/theme instantly)
    const saved = await api.saveSettings(merged);
    setSettings(saved);
  }

  function addTime() {
    const times = [...settings!.reminder_times, "12:00"];
    patch({ reminder_times: times });
  }
  function setTime(i: number, val: string) {
    const times = settings!.reminder_times.map((t, idx) => (idx === i ? val : t));
    patch({ reminder_times: times });
  }
  function removeTime(i: number) {
    patch({ reminder_times: settings!.reminder_times.filter((_, idx) => idx !== i) });
  }

  async function regenerate() {
    setBusy(true);
    try {
      await api.regeneratePlan();
      await reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("app.name")}</span>
          <h1 className="page-title">{t("settings.title")}</h1>
        </div>
      </header>

      <Card className="stack">
        <div>
          <label className="field-label">{t("settings.language")}</label>
          <Segmented<Lang>
            value={settings.language}
            onChange={(v) => patch({ language: v })}
            options={[
              { value: "en", label: "English" },
              { value: "es", label: "Español" },
            ]}
          />
        </div>
        <div>
          <label className="field-label">{t("settings.theme")}</label>
          <Segmented<Theme>
            value={settings.theme}
            onChange={(v) => patch({ theme: v })}
            options={[
              { value: "light", label: t("settings.themeLight") },
              { value: "dark", label: t("settings.themeDark") },
              { value: "system", label: t("settings.themeSystem") },
            ]}
          />
        </div>
      </Card>

      <Card className="stack">
        <div className="spread">
          <label className="field-label" style={{ margin: 0 }}>{t("settings.remindersOn")}</label>
          <Toggle on={settings.reminder_enabled} onChange={(v) => patch({ reminder_enabled: v })} />
        </div>

        {settings.reminder_enabled && (
          <>
            <div>
              <label className="field-label">{t("settings.reminderTimes")}</label>
              <div className="time-list">
                {settings.reminder_times.map((time, i) => (
                  <div className="time-row" key={i}>
                    <input
                      type="time"
                      className="time-input"
                      value={time}
                      onChange={(e) => setTime(i, e.target.value)}
                    />
                    <button className="time-remove" onClick={() => removeTime(i)} aria-label="remove">✕</button>
                  </div>
                ))}
              </div>
              {settings.reminder_times.length < 3 && (
                <button className="add-time" onClick={addTime}>+ {t("settings.addTime")}</button>
              )}
            </div>

            <div className="spread">
              <label className="field-label" style={{ margin: 0 }}>{t("settings.nag")}</label>
              <Toggle on={settings.nag_enabled} onChange={(v) => patch({ nag_enabled: v })} />
            </div>
            {settings.nag_enabled && (
              <div className="spread">
                <label className="field-label" style={{ margin: 0 }}>{t("settings.nagTime")}</label>
                <input
                  type="time"
                  className="time-input"
                  value={settings.nag_time}
                  onChange={(e) => patch({ nag_time: e.target.value })}
                />
              </div>
            )}
            <p className="muted setting-help">{t("settings.reminderHelp")}</p>
          </>
        )}
      </Card>

      <Card className="stack">
        <div className="spread">
          <div>
            <div className="field-label" style={{ margin: 0 }}>{t("settings.regenerate")}</div>
            <p className="muted setting-help" style={{ margin: "4px 0 0" }}>{t("settings.regenerateHelp")}</p>
          </div>
        </div>
        <Button variant="soft" onClick={regenerate} disabled={busy}>
          {busy ? t("common.loading") : t("settings.regenerate")}
        </Button>
        <Button variant="ghost" onClick={() => nav("/onboarding")}>
          {t("settings.editProfile")}
        </Button>
      </Card>

      <p className="disclaimer" style={{ textAlign: "center" }}>🔒 {t("settings.about")}</p>
    </div>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      className={`toggle ${on ? "toggle-on" : ""}`}
      onClick={() => onChange(!on)}
      role="switch"
      aria-checked={on}
    >
      <span className="toggle-knob" />
    </button>
  );
}
