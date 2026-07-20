"""P1 — schema v3: streak_state, HR columns, recap/exclusion settings,
items_done normalization. See docs/plans/P1-data-migrations.md."""

import sqlite3
import sys
import threading
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))


def _fresh_db_module(monkeypatch, path):
    monkeypatch.setenv("FITINGO_DB", str(path))
    import db

    db._local = threading.local()
    db._schema_ready = False
    return db


def _make_v2_db(path):
    """A database as v1.3.0 shipped it (schema v2), with user data."""
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO meta VALUES ('schema_version', '2');
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            language TEXT DEFAULT 'en', theme TEXT DEFAULT 'system',
            reminder_enabled INTEGER DEFAULT 1,
            reminder_times TEXT DEFAULT '["18:00"]',
            nag_enabled INTEGER DEFAULT 1, nag_time TEXT DEFAULT '21:00',
            water_goal_ml INTEGER DEFAULT 2000,
            water_reminder_enabled INTEGER DEFAULT 0,
            water_interval_min INTEGER DEFAULT 120,
            water_start TEXT DEFAULT '09:00', water_end TEXT DEFAULT '21:00');
        INSERT INTO settings (id, language, water_goal_ml) VALUES (1, 'es', 2500);
        CREATE TABLE workout_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            plan_id INTEGER, completed INTEGER DEFAULT 0, items_done TEXT,
            items_total INTEGER, perceived_difficulty REAL,
            duration_min INTEGER, UNIQUE(date));
        INSERT INTO workout_log (date, completed, items_done, items_total)
            VALUES ('2026-07-01', 1, '["squat"]', 5);
        CREATE TABLE water_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            ml INTEGER NOT NULL DEFAULT 0, UNIQUE(date));
        INSERT INTO water_log (date, ml) VALUES ('2026-07-01', 1500);
    """)
    conn.commit()
    conn.close()


def test_v2_db_migrates_to_v3(tmp_path, monkeypatch):
    path = tmp_path / "v2.db"
    _make_v2_db(path)
    db = _fresh_db_module(monkeypatch, path)
    conn = db.get_conn()

    s = db.get_settings()
    assert s["language"] == "es" and s["water_goal_ml"] == 2500  # data survives
    assert s["weekly_recap_enabled"] is True
    assert s["excluded_exercises"] == []

    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert row["value"] == str(db.SCHEMA_VERSION) == "3"

    st = db.get_streak_state()
    assert st == {"freezes": 0, "frozen_dates": [], "last_earned_week": None}

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(workout_log)")}
    assert {"avg_hr", "max_hr"} <= cols
    # old log row intact
    row = conn.execute("SELECT * FROM workout_log WHERE date='2026-07-01'").fetchone()
    assert row["completed"] == 1 and row["avg_hr"] is None


def test_fresh_db_is_v3(tmp_path, monkeypatch):
    db = _fresh_db_module(monkeypatch, tmp_path / "fresh.db")
    conn = db.get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert row["value"] == "3"
    assert db.get_streak_state()["freezes"] == 0


def test_streak_state_roundtrip_and_clamp(tmp_path, monkeypatch):
    db = _fresh_db_module(monkeypatch, tmp_path / "s.db")
    db.get_conn()
    db.save_streak_state(2, ["2026-07-02", "2026-07-02", "2026-07-04"], "2026-W27")
    st = db.get_streak_state()
    assert st["freezes"] == 2
    assert st["frozen_dates"] == ["2026-07-02", "2026-07-04"]  # deduped, sorted
    assert st["last_earned_week"] == "2026-W27"
    db.save_streak_state(-3, [], None)
    assert db.get_streak_state()["freezes"] == 0  # clamped


def test_excluded_exercises_roundtrip(tmp_path, monkeypatch):
    db = _fresh_db_module(monkeypatch, tmp_path / "e.db")
    db.get_conn()
    assert db.get_excluded_exercises() == []
    db.set_excluded_exercises(["burpee", "burpee", "jump-squat"])
    assert db.get_excluded_exercises() == ["burpee", "jump-squat"]


def test_clear_activity_resets_freezes_keeps_exclusions(tmp_path, monkeypatch):
    db = _fresh_db_module(monkeypatch, tmp_path / "c.db")
    db.get_conn()
    db.save_streak_state(2, ["2026-07-02"], "2026-W27")
    db.set_excluded_exercises(["burpee"])
    db.clear_activity()
    assert db.get_streak_state() == {"freezes": 0, "frozen_dates": [],
                                     "last_earned_week": None}
    assert db.get_excluded_exercises() == ["burpee"]


def test_reset_all_clears_everything(tmp_path, monkeypatch):
    db = _fresh_db_module(monkeypatch, tmp_path / "r.db")
    db.get_conn()
    db.save_streak_state(1, ["2026-07-02"], "2026-W27")
    db.set_excluded_exercises(["burpee"])
    db.reset_all()
    assert db.get_streak_state()["freezes"] == 0
    assert db.get_excluded_exercises() == []


@pytest.mark.parametrize("raw,expected", [
    (["push-up", "squat:main:2"], ["push-up:main:0", "squat:main:2"]),
    ([], []),
    (["a:warmup:0", "b:cooldown:5"], ["a:warmup:0", "b:cooldown:5"]),
])
def test_normalize_item_keys(raw, expected, tmp_path, monkeypatch):
    db = _fresh_db_module(monkeypatch, tmp_path / "n.db")
    assert db.normalize_item_keys(raw) == expected
