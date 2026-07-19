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
import shutil
import subprocess
import threading
import time
from datetime import date, datetime

log = logging.getLogger("fitingo.reminders")

APP_URL = "http://localhost:8777"

MESSAGES = {
    "en": {
        "title": "Fit-ingo",
        "reminder": "Time to move! Your workout is waiting. 💪",
        "nag": "Don't lose your streak! A few minutes is all it takes. 🔥",
        "water": "Hydration check — have a glass of water. 💧",
    },
    "es": {
        "title": "Fit-ingo",
        "reminder": "¡Hora de moverte! Tu entrenamiento te espera. 💪",
        "nag": "¡No pierdas tu racha! Solo te toma unos minutos. 🔥",
        "water": "Momento de hidratarte — toma un vaso de agua. 💧",
    },
}


# Module-level state so the /api/notifications/status endpoint can report on
# the last attempt without threading extra plumbing through the scheduler.
last_fired: str | None = None
last_error: str | None = None


def _termux_available() -> bool:
    return shutil.which("termux-notification") is not None


def get_status() -> dict:
    return {
        "termux_cli": _termux_available(),
        "last_fired": last_fired,
        "last_error": last_error,
    }


def send_notification(title: str, content: str) -> dict:
    """Fire a real Termux notification, or log a stub if not on Termux.

    Returns a status dict ``{"sent": bool, "termux": bool, "error": str|None}``
    and updates the module-level ``last_fired``/``last_error`` state so errors
    are surfaced instead of only logged.
    """
    global last_fired, last_error
    termux = _termux_available()

    if not termux:
        # Dev path: no device to notify, just log. Counts as "sent" so the
        # rest of the flow (dedup, UI feedback) behaves the same as on-device.
        log.info("[notification stub] %s — %s", title, content)
        last_fired = datetime.now().isoformat()
        last_error = None
        return {"sent": True, "termux": False, "error": None}

    try:
        proc = subprocess.run(
            [
                "termux-notification",
                "--id", "fitingo",
                "--title", title,
                "--content", content,
                "--action", f"termux-open-url {APP_URL}",
                "--priority", "high",
            ],
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
                 get_water_today=None):
        self._get_settings = get_settings
        self._get_training_weekdays = get_training_weekdays
        self._is_today_done = is_today_done
        # () -> (ml_drunk, goal_ml); optional so old wiring keeps working.
        self._get_water_today = get_water_today
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # Remembers "YYYY-MM-DD HH:MM kind" strings already fired today.
        self._fired: set[str] = set()
        self._last_day: date | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="reminders", daemon=True)
        self._thread.start()
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
        self._fire(today, hhmm, "water", msg["title"], msg["water"])

    def _fire(self, today: date, hhmm: str, kind: str, title: str, content: str) -> None:
        key = f"{today.isoformat()} {hhmm} {kind}"
        if key in self._fired:
            return
        self._fired.add(key)
        send_notification(title, content)
