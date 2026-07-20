import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Button, Card, Segmented, Stepper } from "../components/ui";
import { APP_VERSION } from "../lib/version";
import type { Lang, Settings as SettingsT, Theme } from "../lib/types";
import "./settings.css";

export function Settings() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { settings, setSettings, setProfile, reload } = useApp();
  const [busy, setBusy] = useState(false);
  const [notifStatus, setNotifStatus] = useState<{
    termux_cli: boolean;
    last_fired: string | null;
    last_error: string | null;
  } | null>(null);
  const [testBusy, setTestBusy] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const restoreRef = useRef<HTMLInputElement>(null);
  const [pendingRestore, setPendingRestore] = useState<File | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  useEffect(() => {
    api.getNotificationStatus().then(setNotifStatus).catch(() => setNotifStatus(null));
  }, []);

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

  async function sendTestNotification() {
    setTestBusy(true);
    setTestResult(null);
    try {
      const res = await api.testNotification();
      if (res.sent) {
        setTestResult({ ok: true, message: t("settings.testSent") });
      } else {
        setTestResult({ ok: false, message: res.error ?? t("settings.testFailed") });
      }
    } catch {
      setTestResult({ ok: false, message: t("settings.testFailed") });
    } finally {
      setTestBusy(false);
    }
  }

  // Force the browser to re-fetch sw.js instead of waiting for it to notice on
  // its own. If a newer build exists it installs, takes over (skipWaiting) and
  // the controllerchange listener in main.tsx reloads onto it. With no update
  // we report the running version, so a stale phone is diagnosable on the spot.
  async function checkForUpdates() {
    setUpdateBusy(true);
    setUpdateMsg(null);
    try {
      if (!("serviceWorker" in navigator)) {
        window.location.reload();
        return;
      }
      const reg = await navigator.serviceWorker.getRegistration();
      if (!reg) {
        window.location.reload();
        return;
      }
      await reg.update(); // re-fetches sw.js, bypassing the HTTP cache

      // Only a page that already has a controller can be out of date; without
      // one this is the first install, which is current by definition.
      const pending = reg.installing || reg.waiting;
      if (navigator.serviceWorker.controller && pending) {
        // sw.js is generated with skipWaiting, so it takes over on its own as
        // soon as it finishes installing — nothing to nudge here.
        setUpdateMsg(t("settings.updateApplying"));
      } else {
        setUpdateMsg(t("settings.upToDate", { version: APP_VERSION }));
      }
    } catch (e) {
      setUpdateMsg(e instanceof Error ? e.message : t("settings.updateFailed"));
    } finally {
      setUpdateBusy(false);
    }
  }

  async function confirmRestore() {
    if (!pendingRestore) return;
    setRestoring(true);
    setRestoreError(null);
    try {
      await api.restoreBackup(pendingRestore);
      // Everything in memory (profile, plan, settings) is now stale.
      window.location.reload();
    } catch (e) {
      setRestoreError(e instanceof Error ? e.message : String(e));
      setRestoring(false);
    }
  }

  async function confirmReset() {
    setResetting(true);
    try {
      await api.resetApp();
      setProfile(null);
      nav("/onboarding", { replace: true });
    } finally {
      setResetting(false);
      setShowResetConfirm(false);
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

        <div className="notif-status">
          {notifStatus ? (
            notifStatus.termux_cli ? (
              <span className="notif-ok">{t("settings.termuxDetected")}</span>
            ) : (
              <span className="notif-warn">{t("settings.termuxMissing")}</span>
            )
          ) : (
            <span className="muted">{t("common.loading")}</span>
          )}
          {notifStatus?.last_error && (
            <p className="muted notif-error">{notifStatus.last_error}</p>
          )}
        </div>
        <Button variant="soft" onClick={sendTestNotification} disabled={testBusy}>
          {testBusy ? t("common.loading") : t("settings.testNotification")}
        </Button>
        {testResult && (
          <p className={testResult.ok ? "notif-ok" : "notif-warn"}>{testResult.message}</p>
        )}
      </Card>

      <Card className="stack">
        <div className="spread">
          <label className="field-label" style={{ margin: 0 }}>💧 {t("water.reminders")}</label>
          <Toggle
            on={settings.water_reminder_enabled}
            onChange={(v) => patch({ water_reminder_enabled: v })}
          />
        </div>
        <div className="spread">
          <label className="field-label" style={{ margin: 0 }}>{t("water.goal")}</label>
          <Stepper
            value={settings.water_goal_ml}
            min={1000}
            max={4000}
            step={250}
            suffix=" ml"
            onChange={(v) => patch({ water_goal_ml: v })}
          />
        </div>
        {settings.water_reminder_enabled && (
          <>
            <div className="spread">
              <label className="field-label" style={{ margin: 0 }}>{t("water.every")}</label>
              <Stepper
                value={settings.water_interval_min}
                min={30}
                max={240}
                step={30}
                suffix=" min"
                onChange={(v) => patch({ water_interval_min: v })}
              />
            </div>
            <div className="spread">
              <label className="field-label" style={{ margin: 0 }}>{t("water.window")}</label>
              <div className="water-window">
                <input
                  type="time"
                  className="time-input"
                  value={settings.water_start}
                  onChange={(e) => patch({ water_start: e.target.value })}
                />
                <span className="muted">–</span>
                <input
                  type="time"
                  className="time-input"
                  value={settings.water_end}
                  onChange={(e) => patch({ water_end: e.target.value })}
                />
              </div>
            </div>
            <p className="muted setting-help">{t("water.help")}</p>
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

      <Card className="stack">
        <div className="spread">
          <label className="field-label" style={{ margin: 0 }}>{t("settings.version")}</label>
          <span className="num version-value">{APP_VERSION}</span>
        </div>
        <Button variant="soft" onClick={checkForUpdates} disabled={updateBusy}>
          {updateBusy ? t("common.loading") : t("settings.checkUpdates")}
        </Button>
        {updateMsg && <p className="muted setting-help">{updateMsg}</p>}
      </Card>

      <Card className="stack">
        <div className="field-label" style={{ margin: 0 }}>💾 {t("backup.title")}</div>
        <a className="btn btn-soft btn-block" href="/api/backup" download>
          {t("backup.download")}
        </a>
        <Button variant="ghost" onClick={() => restoreRef.current?.click()}>
          {t("backup.restore")}
        </Button>
        <input
          ref={restoreRef}
          type="file"
          accept=".db"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setPendingRestore(f);
            e.target.value = "";
          }}
        />
        <p className="muted setting-help">{t("backup.help")}</p>
      </Card>

      <Card className="stack">
        <div>
          <div className="field-label" style={{ margin: 0 }}>{t("settings.reset")}</div>
        </div>
        <Button variant="danger" onClick={() => setShowResetConfirm(true)}>
          {t("settings.reset")}
        </Button>
      </Card>

      <p className="disclaimer" style={{ textAlign: "center" }}>🔒 {t("settings.about")}</p>

      {pendingRestore && (
        <div className="confirm-sheet">
          <div className="confirm-card">
            <h3 className="confirm-title">{t("backup.confirmTitle")}</h3>
            <p className="muted confirm-body">{t("backup.confirmBody")}</p>
            <p className="muted confirm-body num">{pendingRestore.name}</p>
            {restoreError && <p className="notif-warn">{restoreError}</p>}
            <div className="confirm-actions">
              <Button variant="ghost" onClick={() => setPendingRestore(null)} disabled={restoring}>
                {t("common.cancel")}
              </Button>
              <Button variant="violet" onClick={confirmRestore} disabled={restoring}>
                {restoring ? t("common.loading") : t("backup.restore")}
              </Button>
            </div>
          </div>
        </div>
      )}

      {showResetConfirm && (
        <div className="confirm-sheet">
          <div className="confirm-card">
            <h3 className="confirm-title">{t("settings.resetConfirmTitle")}</h3>
            <p className="muted confirm-body">{t("settings.resetConfirmBody")}</p>
            <div className="confirm-actions">
              <Button variant="ghost" onClick={() => setShowResetConfirm(false)} disabled={resetting}>
                {t("common.cancel")}
              </Button>
              <Button variant="danger" onClick={confirmReset} disabled={resetting}>
                {resetting ? t("common.loading") : t("settings.resetConfirm")}
              </Button>
            </div>
          </div>
        </div>
      )}
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
