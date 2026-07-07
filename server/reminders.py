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
    },
    "es": {
        "title": "Fit-ingo",
        "reminder": "¡Hora de moverte! Tu entrenamiento te espera. 💪",
        "nag": "¡No pierdas tu racha! Solo te toma unos minutos. 🔥",
    },
}


def _termux_available() -> bool:
    return shutil.which("termux-notification") is not None


def send_notification(title: str, content: str) -> None:
    """Fire a real Termux notification, or log if not on Termux."""
    if _termux_available():
        try:
            subprocess.run(
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
            )
        except Exception as exc:  # pragma: no cover - device-only path
            log.warning("termux-notification failed: %s", exc)
    else:
        log.info("[notification stub] %s — %s", title, content)


class ReminderScheduler:
    """Owns the background thread. Callbacks decouple it from db/app modules."""

    def __init__(self, get_settings, get_training_weekdays, is_today_done):
        self._get_settings = get_settings
        self._get_training_weekdays = get_training_weekdays
        self._is_today_done = is_today_done
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
        if not settings.get("reminder_enabled"):
            return

        # Only nag on scheduled training days.
        if today.weekday() not in set(self._get_training_weekdays()):
            return
        # Nothing to remind about if it's already done.
        if self._is_today_done():
            return

        lang = settings.get("language", "en")
        msg = MESSAGES.get(lang, MESSAGES["en"])
        hhmm = now.strftime("%H:%M")

        for t in settings.get("reminder_times", []):
            if t == hhmm:
                self._fire(today, hhmm, "reminder", msg["title"], msg["reminder"])

        if settings.get("nag_enabled") and settings.get("nag_time") == hhmm:
            self._fire(today, hhmm, "nag", msg["title"], msg["nag"])

    def _fire(self, today: date, hhmm: str, kind: str, title: str, content: str) -> None:
        key = f"{today.isoformat()} {hhmm} {kind}"
        if key in self._fired:
            return
        self._fired.add(key)
        send_notification(title, content)
