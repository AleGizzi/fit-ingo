import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

from health import aggregate  # noqa: E402
from reminders import water_slots  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FITINGO_DB", str(tmp_path / "wh.db"))
    import db

    db._local = threading.local()
    db._schema_ready = False
    import app as app_module

    db.get_conn()
    return app_module.app.test_client()


# ---- water -----------------------------------------------------------------

def test_water_accumulates_and_clamps(client):
    r = client.get("/api/water").get_json()
    assert r["ml"] == 0 and r["goal_ml"] == 2000

    assert client.post("/api/water", json={"delta_ml": 250}).get_json()["ml"] == 250
    assert client.post("/api/water", json={"delta_ml": 500}).get_json()["ml"] == 750
    # undo past zero clamps
    assert client.post("/api/water", json={"delta_ml": -1000}).get_json()["ml"] == 0


def test_water_settings_roundtrip(client):
    s = client.post("/api/settings", json={
        "water_goal_ml": 2500, "water_reminder_enabled": True,
        "water_interval_min": 90,
    }).get_json()
    assert s["water_goal_ml"] == 2500
    assert s["water_reminder_enabled"] is True
    assert s["water_interval_min"] == 90
    assert client.get("/api/water").get_json()["goal_ml"] == 2500


def test_every_settings_field_round_trips(client):
    """Regression: weekly_recap_enabled was missing from the UPDATE, so its
    toggle silently did nothing. Assert the whole surface persists."""
    before = client.get("/api/settings").get_json()
    changed = {
        "language": "es", "theme": "dark",
        "reminder_enabled": not before["reminder_enabled"],
        "reminder_times": ["07:30", "19:45"],
        "nag_enabled": not before["nag_enabled"], "nag_time": "22:15",
        "water_goal_ml": 3000,
        "water_reminder_enabled": not before["water_reminder_enabled"],
        "water_interval_min": 45,
        "water_start": "08:15", "water_end": "20:45",
        "weekly_recap_enabled": not before["weekly_recap_enabled"],
        "excluded_exercises": ["burpee"],
    }
    client.post("/api/settings", json=changed)
    after = client.get("/api/settings").get_json()
    for key, value in changed.items():
        assert after[key] == value, f"{key} did not persist"


def test_profile_change_clears_water(client):
    client.post("/api/water", json={"delta_ml": 500})
    client.post("/api/profile", json={
        "name": "T", "age": 30, "sex": "male", "height_cm": 170, "weight_kg": 75,
        "goal": "maintain", "level": "beginner", "impact": "low",
        "equipment": "none", "days_per_week": 3, "session_minutes": 30,
        "limitations": [], "diet_pref": "any",
    })
    assert client.get("/api/water").get_json()["ml"] == 0


def test_water_slots():
    assert water_slots("09:00", "21:00", 120) == {
        "09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"}
    assert "09:30" in water_slots("09:00", "10:00", 30)
    assert water_slots("garbage", "21:00", 60) == set()
    # interval floor: 1-minute spam becomes 15-minute
    assert len(water_slots("09:00", "10:00", 1)) == 5


# ---- schema migration -------------------------------------------------------

def test_v1_db_migrates_in_place(tmp_path, monkeypatch):
    """A database created before water/health (schema v1) must gain the new
    columns and tables without losing data."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(str(path))
    old.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO meta VALUES ('schema_version', '1');
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            language TEXT DEFAULT 'en', theme TEXT DEFAULT 'system',
            reminder_enabled INTEGER DEFAULT 1,
            reminder_times TEXT DEFAULT '["18:00"]',
            nag_enabled INTEGER DEFAULT 1, nag_time TEXT DEFAULT '21:00');
        INSERT INTO settings (id, language) VALUES (1, 'es');
    """)
    old.commit()
    old.close()

    monkeypatch.setenv("FITINGO_DB", str(path))
    import db

    db._local = threading.local()
    db._schema_ready = False
    conn = db.get_conn()

    s = db.get_settings()
    assert s["language"] == "es", "existing settings row must survive"
    assert s["water_goal_ml"] == 2000
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert row["value"] == str(db.SCHEMA_VERSION)
    conn.execute("SELECT * FROM water_log")  # table exists
    conn.execute("SELECT * FROM activities")


# ---- FIT aggregation --------------------------------------------------------

def _dt(s):
    return datetime.fromisoformat(s)


def test_aggregate_session_to_activity():
    out = aggregate([{
        "name": "session",
        "fields": {
            "start_time": _dt("2026-07-18T07:30:00"), "sport": "running",
            "total_elapsed_time": 1800.0, "total_distance": 5000.0,
            "avg_heart_rate": 152, "max_heart_rate": 181, "total_calories": 320,
        },
    }], "run.fit")
    [a] = out["activities"]
    assert a["sport"] == "running"
    assert a["duration_min"] == 30.0
    assert a["distance_km"] == 5.0
    assert a["avg_hr"] == 152 and a["max_hr"] == 181 and a["calories"] == 320
    assert a["source_file"] == "run.fit"


def test_aggregate_monitoring_daily_steps():
    """Steps are cumulative through the day: keep the max per date."""
    recs = [
        {"name": "monitoring", "fields": {"timestamp": _dt("2026-07-18T08:00:00"), "steps": 1200}},
        {"name": "monitoring", "fields": {"timestamp": _dt("2026-07-18T20:00:00"), "steps": 9800}},
        {"name": "monitoring", "fields": {"timestamp": _dt("2026-07-19T09:00:00"), "steps": 700}},
        {"name": "monitoring_hr_data",
         "fields": {"timestamp": _dt("2026-07-18T23:59:00"), "resting_heart_rate": 54}},
    ]
    out = aggregate(recs, "wellness.fit")
    assert out["daily"]["2026-07-18"]["steps"] == 9800
    assert out["daily"]["2026-07-18"]["resting_hr"] == 54
    assert out["daily"]["2026-07-19"]["steps"] == 700


def test_aggregate_ignores_junk():
    out = aggregate([
        {"name": "session", "fields": {"sport": "yoga"}},          # no timestamp
        {"name": "monitoring", "fields": {"steps": 5}},            # no timestamp
        {"name": "file_id", "fields": {"type": "activity"}},       # irrelevant
    ], "x.fit")
    assert out["activities"] == [] and out["daily"] == {}


def test_import_endpoint_rejects_garbage(client):
    import io
    r = client.post("/api/health/import", data={
        "files": (io.BytesIO(b"not a fit file"), "junk.fit"),
    }, content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200
    assert body["activities_imported"] == 0
    assert body["errors"] and "junk.fit" in body["errors"][0]


def test_import_endpoint_no_files(client):
    assert client.post("/api/health/import").status_code == 400


def test_health_summary_empty(client):
    s = client.get("/api/health/summary").get_json()
    assert s == {"daily": [], "activities": []}
