import sys
from datetime import date, timedelta
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

from streak import compute_streak  # noqa: E402

# Reference "today": Sunday 2026-07-05. Mon=0..Sun=6.
# Training on Mon(0), Wed(2), Fri(4).
TRAINING = [0, 2, 4]


def d(iso):
    return iso


def test_no_training_days():
    r = compute_streak([], [], today="2026-07-05")
    assert r == {"current": 0, "best": 0, "at_risk": False}


def test_empty_history():
    r = compute_streak([], TRAINING, today="2026-07-05")
    assert r["current"] == 0
    assert r["best"] == 0


def test_rest_days_do_not_break_streak():
    # Completed Mon 06-29, Wed 07-01, Fri 07-03. Today Sun 07-05 (rest).
    # The Tue/Thu/Sat/Sun rest days must not break the run.
    done = ["2026-06-29", "2026-07-01", "2026-07-03"]
    r = compute_streak(done, TRAINING, today="2026-07-05")
    assert r["current"] == 3
    assert r["best"] == 3


def test_missed_training_day_breaks_streak():
    # Missed Wed 07-01. Completed Mon 06-29 and Fri 07-03.
    done = ["2026-06-29", "2026-07-03"]
    r = compute_streak(done, TRAINING, today="2026-07-05")
    # Walking back from Sunday: Fri done (1), Wed missing -> stop.
    assert r["current"] == 1


def test_today_is_training_not_done_does_not_break():
    # Today is Fri 07-03 (a training day) and not yet done.
    # Streak from Mon+Wed should still read as 2, and be at risk.
    done = ["2026-06-29", "2026-07-01"]
    r = compute_streak(done, TRAINING, today="2026-07-03")
    assert r["current"] == 2
    assert r["at_risk"] is True


def test_today_training_done_counts_and_not_at_risk():
    done = ["2026-06-29", "2026-07-01", "2026-07-03"]
    r = compute_streak(done, TRAINING, today="2026-07-03")
    assert r["current"] == 3
    assert r["at_risk"] is False


def test_best_streak_from_history():
    # A 3-run earlier, broken, then a 1-run at the end.
    # Training Mon/Wed/Fri. Done first full week + missed then 1.
    done = [
        "2026-06-15", "2026-06-17", "2026-06-19",   # week: 3
        # skip 06-22 (Mon) -> break
        "2026-06-24", "2026-06-26",                 # Wed, Fri: 2
        # skip 06-29 -> break
        "2026-07-01",                               # Wed: current 1
    ]
    r = compute_streak(done, TRAINING, today="2026-07-01")
    assert r["best"] == 3
    assert r["current"] == 1


def test_daily_training_all_week():
    # Train every day, done every day for 5 days ending today.
    training = [0, 1, 2, 3, 4, 5, 6]
    today = date(2026, 7, 5)
    done = [(today - timedelta(days=i)).isoformat() for i in range(5)]
    r = compute_streak(done, training, today=today.isoformat())
    assert r["current"] == 5
    assert r["best"] == 5


# ---- strict-model regression tests ---------------------------------------
# User-reported bug: completing one training day must not make the *next*
# day look "already done" — the streak should reflect only the day that was
# actually completed until another day is explicitly acted on.

def test_next_rest_day_does_not_inflate_streak():
    # Mon 06-29 completed. Today is Tue 06-30 (a rest day, nothing to do).
    # The streak must still read as exactly 1 — the rest day is not counted
    # and does not "carry forward" any extra credit.
    done = ["2026-06-29"]
    r = compute_streak(done, TRAINING, today="2026-06-30")
    assert r["current"] == 1
    assert r["best"] == 1


def test_next_training_day_not_yet_done_does_not_inflate_streak():
    # Mon 06-29 completed. Today is Wed 07-01 (a training day) but it has NOT
    # been completed yet. The streak must read as 1 (only Monday), not 2 —
    # today isn't over yet so it doesn't break the streak, but it also must
    # not be silently credited.
    done = ["2026-06-29"]
    r = compute_streak(done, TRAINING, today="2026-07-01")
    assert r["current"] == 1
    assert r["at_risk"] is True


def test_missed_wednesday_resets_to_one_walking_back_from_friday():
    # Training Mon/Wed/Fri. Complete Mon, MISS Wed, complete Fri. Walking
    # back from Friday itself (today == Fri, already done), the missed
    # Wednesday must end the run right after Friday: current == 1.
    done = ["2026-06-29", "2026-07-03"]  # Mon, Fri (Wed 07-01 skipped)
    r = compute_streak(done, TRAINING, today="2026-07-03")
    assert r["current"] == 1
    assert r["at_risk"] is False


def test_rest_day_between_two_completed_training_days_keeps_run_intact():
    # Training Mon/Wed/Fri. Complete Mon and Wed; Tue is a rest day sitting
    # between them and must not break or dilute the run.
    done = ["2026-06-29", "2026-07-01"]  # Mon, Wed
    r = compute_streak(done, TRAINING, today="2026-07-01")
    assert r["current"] == 2
    assert r["best"] == 2


def test_fresh_profile_empty_history_has_no_streak():
    # Brand-new profile: no workouts logged yet at all.
    r = compute_streak([], TRAINING, today="2026-07-05")
    assert r["current"] == 0
    assert r["best"] == 0
