"""Duolingo-style streak computation.

A streak counts consecutive *scheduled training days* that were completed.
Scheduled rest days never break the streak — they are simply skipped. A
training day that passes without completion breaks it.

Kept as a pure function over (completed dates, training weekdays, today) so it
can be unit-tested without a database.
"""

from __future__ import annotations

from datetime import date, timedelta


def _parse(d) -> date:
    if isinstance(d, date):
        return d
    return date.fromisoformat(d)


def compute_streak(completed_dates, training_weekdays, today=None) -> dict:
    """Return current + best streak given completion history.

    Args:
        completed_dates: iterable of ISO date strings / date objects that were
            completed.
        training_weekdays: set/list of weekday ints (0=Mon..6=Sun) that are
            scheduled training days.
        today: reference date (defaults to real today).
    """
    if today is None:
        today = date.today()
    else:
        today = _parse(today)

    done = {_parse(d) for d in completed_dates}
    training = set(training_weekdays)

    if not training:
        return {"current": 0, "best": 0, "at_risk": False}

    # ---- current streak: walk backwards from today over training days -----
    current = 0
    cursor = today
    # If today is a training day not yet done, it doesn't break the streak
    # (the day isn't over) — start from the most recent *decided* training day.
    if cursor.weekday() in training and cursor not in done:
        cursor -= timedelta(days=1)

    guard = 0
    while guard < 3650:
        guard += 1
        if cursor.weekday() in training:
            if cursor in done:
                current += 1
            else:
                break
        cursor -= timedelta(days=1)

    # ---- best streak: scan the full history of training days --------------
    best = 0
    run = 0
    if done:
        start = min(done)
        cursor = start
        end = today
        while cursor <= end:
            if cursor.weekday() in training:
                if cursor in done:
                    run += 1
                    best = max(best, run)
                else:
                    run = 0
            cursor += timedelta(days=1)
    best = max(best, current)

    # ---- at risk? today is a training day, not yet done -------------------
    at_risk = today.weekday() in training and today not in done and current > 0

    return {"current": current, "best": best, "at_risk": at_risk}
