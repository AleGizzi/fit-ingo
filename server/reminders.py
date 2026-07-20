"""Local reminder scheduler.

A daemon thread inside the Flask process wakes every 30 s and, when the wall
clock matches a configured reminder time (to the minute), fires an Android
notification via ``termux-notification`` (from the Termux:API app). On a normal
PC where that binary is absent, it logs the notification instead — so the same
code path is exercised in development.

Reminders only fire when:
  * reminders are enabled in settings, and
  * today is a scheduled training day, and
  * today's workout is not already complete.

A later "streak in danger" nag escalates if the workout is still not done.
Each (time, kind) fires at most once per day.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from datetime import date, datetime

log = logging.getLogger("fitingo.reminders")

APP_PORT = os.environ.get("FITINGO_PORT", "8777")
APP_URL = f"http://localhost:{APP_PORT}"

MESSAGES = {
    "en": {
        "title": "Fit-ingo",
        "reminder": "Time to move! Your workout is waiting. 💪",
        "nag": "Don't lose your streak! A few minutes is all it takes. 🔥",
        "water": "Hydration check — have a glass of water. 💧",
        "water_button": "+250 ml",
        "recap": ("This week: {done}/{planned} workouts · {liters} L water · "
                  "streak {streak} 🔥"),
    },
    "es": {
        "title": "Fit-ingo",
        "reminder": "¡Hora de moverte! Tu entrenamiento te espera. 💪",
        "nag": "¡No pierdas tu racha! Solo te toma unos minutos. 🔥",
        "water": "Momento de hidratarte — toma un vaso de agua. 💧",
        "water_button": "+250 ml",
        "recap": ("Esta semana: {done}/{planned} entrenos · {liters} L de agua · "
                  "racha {streak} 🔥"),
    },
}


# Module-level state so the /api/notifications/status endpoint can report on
# the last attempt without threading extra plumbing through the scheduler.
last_fired: str | None = None
last_error: str | None = None
last_tick: str | None = None
last_buttons: list[str] = []


def _termux_available() -> bool:
    return shutil.which("termux-notification") is not None


def get_status() -> dict:
    return {
        "termux_cli": _termux_available(),
        "last_fired": last_fired,
        "last_error": last_error,
        "last_tick": last_tick,
    }


def send_notification(title: str, content: str,
                      buttons: list[tuple[str, str]] | None = None) -> dict:
    """Fire a real Termux notification, or log a stub if not on Termux.

    ``buttons`` is up to 3 (label, shell command) pairs rendered as action
    buttons in the notification shade — Termux runs the command in its own
    shell when tapped.

    Returns a status dict ``{"sent": bool, "termux": bool, "error": str|None}``
    and updates the module-level ``last_fired``/``last_error`` state so errors
    are surfaced instead of only logged.
    """
    global last_fired, last_error, last_buttons
    termux = _termux_available()
    buttons = (buttons or [])[:3]  # termux supports button1..button3
    last_buttons = [label for label, _cmd in buttons]

    if not termux:
        # Dev path: no device to notify, just log. Counts as "sent" so the
        # rest of the flow (dedup, UI feedback) behaves the same as on-device.
        log.info("[notification stub] %s — %s %s", title, content,
                 f"buttons={last_buttons}" if last_buttons else "")
        last_fired = datetime.now().isoformat()
        last_error = None
        return {"sent": True, "termux": False, "error": None}

    cmd = [
        "termux-notification",
        "--id", "fitingo",
        "--title", title,
        "--content", content,
        "--action", f"termux-open-url {APP_URL}",
        "--priority", "high",
    ]
    for i, (label, action) in enumerate(buttons, start=1):
        cmd += [f"--button{i}", label, f"--button{i}-action", action]

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            timeout=15,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            error = f"termux-notification exited {proc.returncode}: {proc.stderr.strip()}"
            log.warning(error)
            last_error = error
            return {"sent": False, "termux": True, "error": error}
        last_fired = datetime.now().isoformat()
        last_error = None
        return {"sent": True, "termux": True, "error": None}
    except Exception as exc:  # pragma: no cover - device-only path
        error = f"termux-notification failed: {exc}"
        log.warning(error)
        last_error = error
        return {"sent": False, "termux": True, "error": error}


RECAP_TIME = "19:00"  # Sunday evening; fixed, not user-configurable


def water_slots(start: str, end: str, interval_min: int) -> set[str]:
    """HH:MM times at which a water reminder is due: start, start+interval, …
    up to and including end. Defensive about bad input (empty on nonsense)."""
    try:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
    except (ValueError, AttributeError):
        return set()
    interval = max(15, int(interval_min or 120))  # floor: never spam < 15 min
    t, stop = sh * 60 + sm, eh * 60 + em
    slots = set()
    while t <= stop:
        slots.add(f"{t // 60:02d}:{t % 60:02d}")
        t += interval
    return slots


class ReminderScheduler:
    """Owns the background thread. Callbacks decouple it from db/app modules."""

    def __init__(self, get_settings, get_training_weekdays, is_today_done,
                 get_water_today=None, nightly_backup=None, get_recap=None):
        self._get_settings = get_settings
        self._get_training_weekdays = get_training_weekdays
        self._is_today_done = is_today_done
        # () -> (ml_drunk, goal_ml); optional so old wiring keeps working.
        self._get_water_today = get_water_today
        # () -> None, runs once a night; optional.
        self._nightly_backup = nightly_backup
        # () -> {done, planned, liters, streak}; optional.
        self._get_recap = get_recap
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # Remembers "YYYY-MM-DD HH:MM kind" strings already fired today.
        self._fired: set[str] = set()
        self._last_day: date | None = None

    def start(self) -> None:
        global last_tick
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="reminders", daemon=True)
        self._thread.start()
        # Mark the heartbeat immediately: the first _tick is 30 s away, and
        # until then the status endpoint would report the engine as dead.
        last_tick = datetime.now().isoformat()
        log.info("Reminder scheduler started (termux=%s)", _termux_available())

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(30):
            try:
                self._tick(datetime.now())
            except Exception:  # keep the thread alive no matter what
                log.exception("reminder tick failed")

    def _tick(self, now: datetime) -> None:
        global last_tick
        last_tick = now.isoformat()
        today = now.date()
        if today != self._last_day:
            self._fired.clear()
            self._last_day = today

        settings = self._get_settings()
        lang = settings.get("language", "en")
        msg = MESSAGES.get(lang, MESSAGES["en"])
        hhmm = now.strftime("%H:%M")

        self._tick_workout(settings, today, hhmm, msg)
        self._tick_water(settings, today, hhmm, msg)
        self._tick_recap(settings, today, hhmm, msg)
        self._tick_backup(today, hhmm)

    def _tick_recap(self, settings: dict, today: date, hhmm: str, msg: dict) -> None:
        """Sunday evening summary. Unlike the nags this is a report, so it
        fires regardless of rest days or whether today's workout is done."""
        if not settings.get("weekly_recap_enabled") or not self._get_recap:
            return
        if today.weekday() != 6 or hhmm != RECAP_TIME:
            return
        try:
            data = self._get_recap()
        except Exception:
            log.exception("recap data failed")
            return
        self._fire(today, hhmm, "recap", msg["title"],
                   msg["recap"].format(**data))

    def _tick_backup(self, today: date, hhmm: str) -> None:
        """Nightly local snapshot at 03:00. A failing backup must never take
        the reminder thread down with it."""
        if not self._nightly_backup or not hhmm.startswith("03:0"):
            return
        key = f"{today.isoformat()} backup"
        if key in self._fired:
            return
        self._fired.add(key)
        try:
            self._nightly_backup()
        except Exception:
            log.exception("nightly backup failed")

    def _tick_workout(self, settings: dict, today: date, hhmm: str, msg: dict) -> None:
        if not settings.get("reminder_enabled"):
            return
        # Only nag on scheduled training days.
        if today.weekday() not in set(self._get_training_weekdays()):
            return
        # Nothing to remind about if it's already done.
        if self._is_today_done():
            return

        for t in settings.get("reminder_times", []):
            if t == hhmm:
                self._fire(today, hhmm, "reminder", msg["title"], msg["reminder"])

        if settings.get("nag_enabled") and settings.get("nag_time") == hhmm:
            self._fire(today, hhmm, "nag", msg["title"], msg["nag"])

    def _tick_water(self, settings: dict, today: date, hhmm: str, msg: dict) -> None:
        """Every ``water_interval_min`` inside the waking window, until the
        daily goal is reached. Fires on every day — hydration has no rest days."""
        if not settings.get("water_reminder_enabled") or not self._get_water_today:
            return
        if hhmm not in water_slots(settings.get("water_start", "09:00"),
                                   settings.get("water_end", "21:00"),
                                   int(settings.get("water_interval_min") or 120)):
            return
        ml, goal = self._get_water_today()
        if ml >= goal:
            return
        # Log the drink straight from the notification shade — no app needed.
        log_250 = (
            "curl -s -X POST -H 'Content-Type: application/json' "
            f"-d '{{\"delta_ml\":250}}' {APP_URL}/api/water"
        )
        self._fire(today, hhmm, "water", msg["title"], msg["water"],
                   buttons=[(msg["water_button"], log_250)])

    def _fire(self, today: date, hhmm: str, kind: str, title: str, content: str,
              buttons: list[tuple[str, str]] | None = None) -> None:
        key = f"{today.isoformat()} {hhmm} {kind}"
        if key in self._fired:
            return
        self._fired.add(key)
        send_notification(title, content, buttons=buttons)
