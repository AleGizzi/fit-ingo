"""P2 — streak freezes. See docs/plans/P2-streak-freezes.md.

Pure-function tests use Mon/Wed/Fri (0,2,4) training weeks. API tests drive
the real endpoints with backdated logs.
"""

import sys
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

from streak import compute_streak, consume_freezes, week_complete  # noqa: E402

TRAINING = [0, 2, 4]  # Mon, Wed, Fri


# ---- consume_freezes (pure) -------------------------------------------------

def test_single_miss_bridged():
    # Mon 6th & Wed 8th done, Fri 10th missed, today Sun 12th.
    done = ["2026-07-06", "2026-07-08"]
    left, frozen, changed = consume_freezes(done, TRAINING, 1, [], today="2026-07-12")
    assert changed and left == 0 and frozen == ["2026-07-10"]
    s = compute_streak(done, TRAINING, today="2026-07-12", frozen_dates=frozen)
    assert s["current"] == 2  # frozen day gives continuity, not a count

    # second evaluation: nothing more to consume, no double-spend
    left2, frozen2, changed2 = consume_freezes(done, TRAINING, left, frozen, today="2026-07-12")
    assert not changed2 and left2 == 0 and frozen2 == frozen


def test_two_miss_gap_with_one_freeze_not_wasted():
    # Wed 8th & Fri 10th missed, only Mon 6th done; 1 freeze can't bridge 2.
    done = ["2026-07-06"]
    left, frozen, changed = consume_freezes(done, TRAINING, 1, [], today="2026-07-12")
    assert not changed and left == 1 and frozen == []  # freeze preserved
    s = compute_streak(done, TRAINING, today="2026-07-12")
    assert s["current"] == 0  # broken, honestly


def test_two_miss_gap_with_two_freezes_bridges():
    done = ["2026-07-06"]
    left, frozen, changed = consume_freezes(done, TRAINING, 2, [], today="2026-07-12")
    assert changed and left == 0 and set(frozen) == {"2026-07-08", "2026-07-10"}
    s = compute_streak(done, TRAINING, today="2026-07-12", frozen_dates=frozen)
    assert s["current"] == 1


def test_no_completions_never_consumes():
    left, frozen, changed = consume_freezes([], TRAINING, 2, [], today="2026-07-12")
    assert not changed and left == 2


def test_today_incomplete_is_not_a_miss():
    # Today is Friday 10th, not done; Mon+Wed done. Nothing to freeze.
    done = ["2026-07-06", "2026-07-08"]
    left, frozen, changed = consume_freezes(done, TRAINING, 2, [], today="2026-07-10")
    assert not changed and left == 2
    s = compute_streak(done, TRAINING, today="2026-07-10")
    assert s["current"] == 2 and s["at_risk"]


def test_rest_days_ignored():
    # Gap spans a weekend: Sat/Sun are rest, only Fri is a miss.
    done = ["2026-07-06", "2026-07-08"]  # Mon, Wed
    left, frozen, changed = consume_freezes(done, TRAINING, 2, [], today="2026-07-13")
    assert changed and frozen == ["2026-07-10"] and left == 1


def test_lazy_consumption_is_time_consistent():
    """Bridging the newest gap must give the same outcome whether the streak
    was evaluated the morning after the miss or days later: miss Wed 1st,
    then train Fri 3rd + Mon 6th — the freeze still covers Wed 1st."""
    done = ["2026-06-29", "2026-07-03", "2026-07-06"]  # Mon, Fri, Mon
    left, frozen, changed = consume_freezes(done, TRAINING, 2, [], today="2026-07-07")
    assert changed and left == 1 and frozen == ["2026-07-01"]
    s = compute_streak(done, TRAINING, today="2026-07-07", frozen_dates=frozen)
    assert s["current"] == 3  # Jun 29 + (frozen) + Jul 3 + Jul 6


def test_only_newest_gap_is_bridged():
    """Two gaps: freezes repair the one nearest today; the older break stays
    (it already ended a streak the user saw end)."""
    #  Mon 22nd done | Wed 24th MISS | Fri 26th done | Mon 29th MISS | Wed 1st done
    done = ["2026-06-22", "2026-06-26", "2026-07-01"]
    left, frozen, changed = consume_freezes(done, TRAINING, 1, [], today="2026-07-02")
    assert changed and frozen == ["2026-06-29"] and left == 0
    s = compute_streak(done, TRAINING, today="2026-07-02", frozen_dates=frozen)
    assert s["current"] == 2  # Jun 26 + Jul 1; the Jun 24 break stands


# ---- week_complete (pure) ----------------------------------------------------

def test_week_complete_counts_frozen():
    # Week of Mon 6th: Mon done, Wed frozen, today Fri 10th done.
    done = ["2026-07-06", "2026-07-10"]
    assert week_complete(done, TRAINING, ["2026-07-08"], today="2026-07-10")
    assert not week_complete(done, TRAINING, [], today="2026-07-10")


def test_week_complete_midweek():
    # Wednesday: Mon+Wed done => scheduled-so-far complete (Fri not due yet).
    done = ["2026-07-06", "2026-07-08"]
    assert week_complete(done, TRAINING, [], today="2026-07-08")


# ---- API level ---------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FITINGO_DB", str(tmp_path / "fz.db"))
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


def _training_days(client):
    plan = client.get("/api/plan").get_json()
    return sorted(d["weekday"] for d in plan["days"] if not d["is_rest"])


def _dates_for_weekdays(weekdays, weeks_back):
    """ISO dates of the given weekdays in the week `weeks_back` weeks ago."""
    today = date.today()
    monday = today - timedelta(days=today.weekday(), weeks=weeks_back)
    return [(monday + timedelta(days=w)).isoformat() for w in weekdays]


def test_earn_once_per_week_and_cap(client):
    tw = _training_days(client)
    # Complete last week's full schedule via backdated logs.
    for d in _dates_for_weekdays(tw, 1):
        r = client.post("/api/log", json={
            "date": d, "completed": True, "items_done": [], "items_total": 5})
        assert r.status_code == 200
    # Earning is evaluated against the CURRENT week, so backdated completions
    # of a past week don't earn (by design: freezes reward finishing *this*
    # week). Now complete this week's due days.
    due = [d for d in _dates_for_weekdays(tw, 0) if d <= date.today().isoformat()]
    earned_flags = []
    for d in due:
        r = client.post("/api/log", json={
            "date": d, "completed": True, "items_done": [], "items_total": 5})
        earned_flags.append(r.get_json()["freeze_earned"])
    if due:  # at least one training day has occurred this week
        assert earned_flags[-1] is True, "final due day should earn"
        assert sum(earned_flags) == 1, "exactly one earn per week"
        # repeat the last POST — no second earn
        r = client.post("/api/log", json={
            "date": due[-1], "completed": True, "items_done": [], "items_total": 5})
        assert r.get_json()["freeze_earned"] is False
        assert r.get_json()["streak"]["freezes"] == 1


def test_streak_payload_has_freeze_fields(client):
    s = client.get("/api/streak").get_json()
    assert set(s) >= {"current", "best", "at_risk", "freezes", "frozen_dates"}


def test_profile_change_resets_freezes(client):
    import db
    db.save_streak_state(2, ["2026-07-01"], "2026-W27")
    client.post("/api/profile", json={
        "name": "T2", "age": 31, "sex": "male", "height_cm": 170, "weight_kg": 74,
        "goal": "lose", "level": "beginner", "impact": "low",
        "equipment": "none", "days_per_week": 3, "session_minutes": 30,
        "limitations": [], "diet_pref": "any",
    })
    s = client.get("/api/streak").get_json()
    assert s["freezes"] == 0 and s["frozen_dates"] == []
