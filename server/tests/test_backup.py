"""P6 — backup / restore / nightly snapshots. See docs/plans/P6.

The load-bearing property: a rejected or failed restore must always leave the
app with a working database.
"""

import io
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

PROFILE = {
    "name": "Alice", "age": 30, "sex": "female", "height_cm": 165,
    "weight_kg": 60, "goal": "maintain", "level": "beginner", "impact": "low",
    "equipment": "none", "days_per_week": 3, "session_minutes": 30,
    "limitations": [], "diet_pref": "any",
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FITINGO_DB", str(tmp_path / "data" / "live.db"))
    import db

    db._local = threading.local()
    db._schema_ready = False
    import app as app_module

    db.get_conn()
    return db, app_module.app.test_client(), tmp_path


def test_backup_download_is_a_usable_database(env):
    _db, client, tmp_path = env
    client.post("/api/profile", json=PROFILE)

    r = client.get("/api/backup")
    assert r.status_code == 200
    assert "fitingo-backup-" in r.headers["Content-Disposition"]

    out = tmp_path / "downloaded.db"
    out.write_bytes(r.data)
    conn = sqlite3.connect(str(out))
    names = {x[0] for x in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"profile", "settings", "workout_log", "exercises"} <= names
    assert conn.execute("SELECT name FROM profile WHERE id=1").fetchone()[0] == "Alice"
    conn.close()
    # temp file cleaned up
    assert not list((tmp_path / "data").glob(".backup-*.db"))


def test_restore_round_trip(env):
    db, client, tmp_path = env
    client.post("/api/profile", json=PROFILE)
    client.post("/api/water", json={"delta_ml": 750})
    backup = tmp_path / "alice.db"
    backup.write_bytes(client.get("/api/backup").data)

    # move on with different data
    client.post("/api/profile", json={**PROFILE, "name": "Bob", "weight_kg": 80})
    client.post("/api/water", json={"delta_ml": 250})
    assert client.get("/api/profile").get_json()["name"] == "Bob"

    r = client.post("/api/restore", data={"file": (io.BytesIO(backup.read_bytes()), "b.db")},
                    content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json() == {"ok": True}

    prof = client.get("/api/profile").get_json()
    assert prof["name"] == "Alice" and prof["weight_kg"] == 60
    assert client.get("/api/water").get_json()["ml"] == 750


@pytest.mark.parametrize("payload,label", [
    (b"this is not a database at all", "garbage"),
    (None, "valid-sqlite-wrong-schema"),
])
def test_restore_rejects_bad_files_without_touching_live_db(env, payload, label, tmp_path):
    _db, client, _ = env
    client.post("/api/profile", json=PROFILE)

    if payload is None:
        other = tmp_path / "other.db"
        conn = sqlite3.connect(str(other))
        conn.execute("CREATE TABLE unrelated (x INTEGER)")
        conn.commit()
        conn.close()
        payload = other.read_bytes()

    r = client.post("/api/restore",
                    data={"file": (io.BytesIO(payload), "bad.db")},
                    content_type="multipart/form-data")
    assert r.status_code == 400, label
    assert "error" in r.get_json()
    # live database still works and still holds our data
    assert client.get("/api/profile").get_json()["name"] == "Alice"
    assert client.get("/api/today").status_code == 200


def test_restore_of_older_schema_migrates(env, tmp_path):
    db, client, _ = env
    # a v2-era backup: no streak_state, no hr columns, no recap settings
    old = tmp_path / "v2.db"
    conn = sqlite3.connect(str(old))
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
        INSERT INTO settings (id, language) VALUES (1, 'es');
        CREATE TABLE profile (id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT,
            age INTEGER, sex TEXT, height_cm REAL, weight_kg REAL, goal TEXT,
            level TEXT, impact TEXT, equipment TEXT, days_per_week INTEGER,
            session_minutes INTEGER, limitations TEXT, diet_pref TEXT,
            created_at TEXT, updated_at TEXT);
        INSERT INTO profile (id, name, limitations) VALUES (1, 'Legacy', '[]');
        CREATE TABLE workout_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL, plan_id INTEGER, completed INTEGER DEFAULT 0,
            items_done TEXT, items_total INTEGER, perceived_difficulty REAL,
            duration_min INTEGER, UNIQUE(date));
        CREATE TABLE exercises (id TEXT PRIMARY KEY, name_en TEXT, name_es TEXT,
            instructions_en TEXT, instructions_es TEXT, video_url TEXT,
            muscle_groups TEXT, type TEXT, impact TEXT, difficulty INTEGER,
            equipment TEXT, contraindications TEXT);
    """)
    conn.commit()
    conn.close()

    r = client.post("/api/restore",
                    data={"file": (io.BytesIO(old.read_bytes()), "v2.db")},
                    content_type="multipart/form-data")
    assert r.status_code == 200

    s = client.get("/api/settings").get_json()
    assert s["language"] == "es"          # restored data survived
    assert s["water_goal_ml"] == 2000
    assert s["weekly_recap_enabled"] is True   # migrated column present
    assert client.get("/api/streak").get_json()["freezes"] == 0
    assert client.get("/api/profile").get_json()["name"] == "Legacy"


def test_prune_backups_keeps_newest_seven(env, tmp_path):
    db, _client, _ = env
    d = tmp_path / "backups"
    d.mkdir()
    for day in range(1, 11):
        (d / f"fitingo-202607{day:02d}.db").write_bytes(b"x")
    removed = db.prune_backups(d, keep=7)
    remaining = sorted(p.name for p in d.glob("fitingo-*.db"))
    assert len(remaining) == 7 and len(removed) == 3
    assert remaining[0] == "fitingo-20260704.db"   # oldest three dropped
    assert "fitingo-20260710.db" in remaining


def test_nightly_backup_fires_once_at_three_am(env, tmp_path):
    _db, _client, _ = env
    from reminders import ReminderScheduler

    calls = []
    sched = ReminderScheduler(
        get_settings=lambda: {"reminder_enabled": False, "language": "en"},
        get_training_weekdays=lambda: [0],
        is_today_done=lambda: False,
        nightly_backup=lambda: calls.append(1),
    )
    sched._tick(datetime(2026, 7, 20, 2, 59))
    assert calls == []
    sched._tick(datetime(2026, 7, 20, 3, 0))
    sched._tick(datetime(2026, 7, 20, 3, 1))   # same night → no second run
    assert calls == [1]
    sched._tick(datetime(2026, 7, 21, 3, 0))   # next night → runs again
    assert calls == [1, 1]


def test_nightly_backup_failure_does_not_kill_the_thread(env):
    _db, _client, _ = env
    from reminders import ReminderScheduler

    def boom():
        raise OSError("disk full")

    sched = ReminderScheduler(
        get_settings=lambda: {"reminder_enabled": False, "language": "en"},
        get_training_weekdays=lambda: [0],
        is_today_done=lambda: False,
        nightly_backup=boom,
    )
    sched._tick(datetime(2026, 7, 20, 3, 0))   # must not raise


def test_concurrency_still_sane_after_restore(env, tmp_path):
    """Connections must reopen cleanly against the swapped file."""
    _db, client, _ = env
    client.post("/api/profile", json=PROFILE)
    backup = io.BytesIO(client.get("/api/backup").data)
    assert client.post("/api/restore", data={"file": (backup, "b.db")},
                       content_type="multipart/form-data").status_code == 200

    failures = []

    def hammer():
        for i in range(40):
            if client.get("/api/settings").status_code != 200:
                failures.append("read")
            if client.post("/api/water", json={"delta_ml": 10}).status_code != 200:
                failures.append("write")

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert failures == []
