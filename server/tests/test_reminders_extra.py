"""P7 — weekly recap, water action buttons, scheduler heartbeat.
See docs/plans/P7-notifications-upgrades.md."""

import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

import reminders  # noqa: E402
from reminders import ReminderScheduler  # noqa: E402

# The scheduler tests stub send_notification (autouse fixture below); the two
# tests that exercise the real command-building keep this handle.
REAL_SEND = reminders.send_notification

BASE_SETTINGS = {
    "reminder_enabled": False, "language": "en", "weekly_recap_enabled": True,
    "water_reminder_enabled": False, "reminder_times": [], "nag_enabled": False,
}

RECAP = {"done": 2, "planned": 3, "liters": 3.5, "streak": 4}

# 2026-07-19 is a Sunday, 2026-07-20 a Monday.
SUNDAY_19 = datetime(2026, 7, 19, 19, 0)


def _sched(settings=None, **kw):
    return ReminderScheduler(
        get_settings=lambda: {**BASE_SETTINGS, **(settings or {})},
        get_training_weekdays=lambda: [0, 2, 4],
        is_today_done=lambda: False,
        **kw,
    )


@pytest.fixture(autouse=True)
def capture_notifications(monkeypatch):
    sent = []
    monkeypatch.setattr(reminders, "send_notification",
                        lambda title, content, buttons=None:
                            sent.append((title, content, buttons or [])) or
                            {"sent": True, "termux": False, "error": None})
    return sent


# ---- weekly recap ----------------------------------------------------------

def test_recap_fires_once_on_sunday_evening(capture_notifications):
    s = _sched(get_recap=lambda: RECAP)
    s._tick(datetime(2026, 7, 19, 18, 59))
    assert capture_notifications == []
    s._tick(SUNDAY_19)
    s._tick(SUNDAY_19)  # same minute again → deduped
    assert len(capture_notifications) == 1
    _title, content, _buttons = capture_notifications[0]
    assert "2/3 workouts" in content and "3.5 L" in content and "streak 4" in content


def test_recap_not_on_other_days(capture_notifications):
    s = _sched(get_recap=lambda: RECAP)
    s._tick(datetime(2026, 7, 20, 19, 0))   # Monday
    assert capture_notifications == []


def test_recap_respects_toggle(capture_notifications):
    s = _sched({"weekly_recap_enabled": False}, get_recap=lambda: RECAP)
    s._tick(SUNDAY_19)
    assert capture_notifications == []


def test_recap_spanish(capture_notifications):
    s = _sched({"language": "es"}, get_recap=lambda: RECAP)
    s._tick(SUNDAY_19)
    content = capture_notifications[0][1]
    assert "Esta semana" in content and "2/3 entrenos" in content


def test_recap_survives_data_failure(capture_notifications):
    def boom():
        raise RuntimeError("db gone")

    s = _sched(get_recap=boom)
    s._tick(SUNDAY_19)          # must not raise
    assert capture_notifications == []


def test_recap_fires_even_when_workout_done(capture_notifications):
    """It's a report, not a nag — rest days and finished days still get it."""
    s = ReminderScheduler(
        get_settings=lambda: BASE_SETTINGS,
        get_training_weekdays=lambda: [0, 2, 4],
        is_today_done=lambda: True,
        get_recap=lambda: RECAP,
    )
    s._tick(SUNDAY_19)   # Sunday is a rest day in this schedule
    assert len(capture_notifications) == 1


# ---- water action button ---------------------------------------------------

def test_water_nag_carries_the_button(capture_notifications):
    s = _sched(
        {"water_reminder_enabled": True, "water_start": "09:00",
         "water_end": "21:00", "water_interval_min": 120, "water_goal_ml": 2000},
        get_water_today=lambda: (500, 2000),
    )
    s._tick(datetime(2026, 7, 20, 11, 0))
    assert len(capture_notifications) == 1
    _title, _content, buttons = capture_notifications[0]
    assert len(buttons) == 1
    label, action = buttons[0]
    assert label == "+250 ml"
    assert "/api/water" in action and '"delta_ml":250' in action


def test_workout_reminder_has_no_buttons(capture_notifications):
    s = _sched({"reminder_enabled": True, "reminder_times": ["18:00"]})
    s._tick(datetime(2026, 7, 20, 18, 0))   # Monday, a training day
    assert len(capture_notifications) == 1
    assert capture_notifications[0][2] == []


def test_water_nag_silent_once_goal_reached(capture_notifications):
    s = _sched(
        {"water_reminder_enabled": True, "water_start": "09:00",
         "water_end": "21:00", "water_interval_min": 120, "water_goal_ml": 2000},
        get_water_today=lambda: (2000, 2000),
    )
    s._tick(datetime(2026, 7, 20, 11, 0))
    assert capture_notifications == []


def test_send_notification_builds_button_flags(monkeypatch):
    """The real (on-device) path must pass --button1/--button1-action."""
    calls = {}

    class Proc:
        returncode = 0
        stderr = ""

    def fake_run(cmd, **_kw):
        calls["cmd"] = cmd
        return Proc()

    monkeypatch.setattr(reminders.shutil, "which", lambda _n: "/usr/bin/termux-notification")
    monkeypatch.setattr(reminders.subprocess, "run", fake_run)
    res = REAL_SEND("T", "C", buttons=[("+250 ml", "curl x")])
    assert res["sent"] and res["termux"]
    cmd = calls["cmd"]
    assert "--button1" in cmd and cmd[cmd.index("--button1") + 1] == "+250 ml"
    assert "--button1-action" in cmd and cmd[cmd.index("--button1-action") + 1] == "curl x"


def test_send_notification_caps_at_three_buttons(monkeypatch):
    monkeypatch.setattr(reminders.shutil, "which", lambda _n: None)  # stub path
    REAL_SEND("T", "C", buttons=[(f"b{i}", "x") for i in range(5)])
    assert reminders.last_buttons == ["b0", "b1", "b2"]


# ---- heartbeat -------------------------------------------------------------

def test_heartbeat_updates_on_every_tick():
    reminders.last_tick = None
    s = _sched()
    s._tick(datetime(2026, 7, 20, 10, 0))
    assert reminders.last_tick == "2026-07-20T10:00:00"
    assert reminders.get_status()["last_tick"] == "2026-07-20T10:00:00"
    s._tick(datetime(2026, 7, 20, 10, 0, 30))
    assert reminders.last_tick == "2026-07-20T10:00:30"


def test_status_shape():
    assert set(reminders.get_status()) == {
        "termux_cli", "last_fired", "last_error", "last_tick"}
