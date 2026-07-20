"""P4 — /api/history + lifetime totals. See docs/plans/P4."""

import json
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FITINGO_DB", str(tmp_path / "h.db"))
    import db

    db._local = threading.local()
    db._schema_ready = False
    import app as app_module

    db.get_conn()
    c = app_module.app.test_client()
    c.post("/api/profile", json={
        "name": "T", "age": 30, "sex": "male", "height_cm": 170, "weight_kg": 75,
        "goal": "maintain", "level": "beginner", "impact": "low",
        "equipment": "none", "days_per_week": 3, "session_minutes": 30,
        "limitations": [], "diet_pref": "any",
    })
    return c


def _training_dates(client, n=2):
    """Recent past dates that fall on the plan's training weekdays."""
    plan = client.get("/api/plan").get_json()
    tw = sorted(d["weekday"] for d in plan["days"] if not d["is_rest"])
    out, cursor = [], date.today() - timedelta(days=1)
    while len(out) < n:
        if cursor.weekday() in tw:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return out, tw


def _day_keys(client, d: date):
    plan = client.get("/api/plan").get_json()
    day = next(x for x in plan["days"] if x["weekday"] == d.weekday())
    return [f"{it['exercise_id']}:{it['block']}:{it['position']}" for it in day["items"]], day["items"]


def test_history_modern_keys(client):
    (d1,), _tw = (_training_dates(client, 1))[0], None
    keys, plan_items = _day_keys(client, d1)
    done = keys[:3]
    client.post("/api/log", json={"date": d1.isoformat(), "completed": True,
                                  "items_done": done, "items_total": len(keys)})
    h = client.get("/api/history").get_json()
    entry = next(e for e in h if e["date"] == d1.isoformat())
    assert len(entry["items"]) == len(plan_items)
    assert sum(1 for i in entry["items"] if i["done"]) == 3
    assert {"avg_hr", "max_hr", "perceived_difficulty"} <= set(entry)


def test_history_legacy_bare_ids(client):
    """Old rows hold plain exercise ids — must render, not 500."""
    (d1,), _ = (_training_dates(client, 1))[0], None
    import db
    conn = db.get_conn()
    with db._lock:
        conn.execute(
            "INSERT INTO workout_log(date, plan_id, completed, items_done, items_total) "
            "VALUES (?, (SELECT id FROM plan WHERE active=1), 1, ?, 5)",
            (d1.isoformat(), json.dumps(["squat", "push-up"])),
        )
        conn.commit()
    r = client.get("/api/history")
    assert r.status_code == 200
    entry = next(e for e in r.get_json() if e["date"] == d1.isoformat())
    # legacy keys become 'id:main:<idx>' — they may or may not match plan
    # slots, but they always render as done items.
    assert any(i["done"] for i in entry["items"])


def test_history_survives_plan_regeneration(client):
    (d1,), _ = (_training_dates(client, 1))[0], None
    keys, _items = _day_keys(client, d1)
    client.post("/api/log", json={"date": d1.isoformat(), "completed": True,
                                  "items_done": keys, "items_total": len(keys)})
    client.post("/api/plan/regenerate", json={})
    r = client.get("/api/history")
    assert r.status_code == 200
    entry = next(e for e in r.get_json() if e["date"] == d1.isoformat())
    assert entry["items"], "stale keys must still render"
    assert all(i["done"] for i in entry["items"] if i["done"] is True)


def test_totals_math(client):
    dates, _tw = _training_dates(client, 2)
    expected_reps = 0
    for d in dates:
        keys, items = _day_keys(client, d)
        client.post("/api/log", json={"date": d.isoformat(), "completed": True,
                                      "items_done": keys, "items_total": len(keys)})
        for it in items:
            if it["reps"]:
                expected_reps += (it["sets"] or 1) * it["reps"]
    t = client.get("/api/metrics").get_json()["totals"]
    assert t["total_reps"] == expected_reps
    assert t["total_minutes"] > 0
    assert t["weeks_active"] >= 1
    assert t["workouts_completed"] == 2


def test_regenerate_stores_progression_factor(client):
    r = client.post("/api/plan/regenerate", json={}).get_json()
    assert "progression_factor" in r
    assert r["plan"]["meta"]["progression_factor"] == round(r["progression_factor"], 2)
