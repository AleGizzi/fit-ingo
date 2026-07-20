"""Duolingo-style streak computation.

A streak counts consecutive *scheduled training days* that were completed.
Scheduled rest days never break the streak — they are simply skipped. A
training day that passes without completion breaks it, unless that date was
covered by a streak freeze (see below).

Freezes: earned by completing every scheduled day of a week (bank capped at
2), consumed lazily by the API layer which passes the covered dates in as
``frozen_dates``. A frozen day provides *continuity only* — it keeps the run
alive but does not increment it, and it is never shown as "done".

Kept as a pure function over (completed dates, training weekdays, today,
frozen dates) so it can be unit-tested without a database.
"""

from __future__ import annotations

from datetime import date, timedelta


def _parse(d) -> date:
    if isinstance(d, date):
        return d
    return date.fromisoformat(d)


def compute_streak(completed_dates, training_weekdays, today=None,
                   frozen_dates=()) -> dict:
    """Return current + best streak given completion history.

    Strict rule: a scheduled training day counts toward the streak ONLY if
    its date is present in ``completed_dates``. Walking backwards from today,
    the first training day that was NOT completed (and not frozen) ends the
    run immediately (today itself is exempt from breaking the streak until
    its own day is over — see below). Rest days (weekdays not in
    ``training_weekdays``) are skipped entirely: they are never counted and
    never break the streak. Frozen days are skipped the same way — alive,
    but worth zero.

    Args:
        completed_dates: iterable of ISO date strings / date objects that were
            completed.
        training_weekdays: set/list of weekday ints (0=Mon..6=Sun) that are
            scheduled training days.
        today: reference date (defaults to real today).
        frozen_dates: iterable of dates covered by a consumed streak freeze.
    """
    if today is None:
        today = date.today()
    else:
        today = _parse(today)

    done = {_parse(d) for d in completed_dates}
    frozen = {_parse(d) for d in frozen_dates}
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
            elif cursor in frozen:
                pass  # continuity, no increment
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
                elif cursor in frozen:
                    pass  # continuity, no increment
                else:
                    run = 0
            cursor += timedelta(days=1)
    best = max(best, current)

    # ---- at risk? today is a training day, not yet done -------------------
    at_risk = today.weekday() in training and today not in done and current > 0

    return {"current": current, "best": best, "at_risk": at_risk}


def consume_freezes(completed_dates, training_weekdays, freezes: int,
                    frozen_dates, today=None) -> tuple[int, list[str], bool]:
    """Decide which missed days banked freezes should cover (pure).

    Walks back from yesterday (today can't be "missed" while in progress).
    Every missed training day newer than the most recent completion is a
    candidate, oldest-consumption-first so the bridge actually reaches the
    completed history behind it. A freeze is only worth spending if there is
    a completed training day OLDER than the miss — otherwise there is no
    streak behind it to save.

    Returns (freezes_left, frozen_dates_after, changed).
    """
    if today is None:
        today = date.today()
    else:
        today = _parse(today)

    done = {_parse(d) for d in completed_dates}
    frozen = {_parse(d) for d in frozen_dates}
    training = set(training_weekdays)

    if not training or not done or freezes <= 0:
        return freezes, sorted(d.isoformat() for d in frozen), False

    earliest = min(done)
    misses: list[date] = []
    cursor = today - timedelta(days=1)
    while cursor >= earliest:
        if cursor.weekday() in training:
            if cursor in done or cursor in frozen:
                if misses:
                    break  # gap ends at the first covered day — stop scanning
            else:
                misses.append(cursor)
        cursor -= timedelta(days=1)

    if not misses:
        return freezes, sorted(d.isoformat() for d in frozen), False

    # The gap is contiguous (we stopped at the first covered day). It can
    # only be bridged whole: freezes must cover every miss, oldest first,
    # or the streak is broken anyway and spending would be waste.
    if len(misses) > freezes:
        return freezes, sorted(d.isoformat() for d in frozen), False

    for m in misses:
        frozen.add(m)
        freezes -= 1
    return freezes, sorted(d.isoformat() for d in frozen), True


def week_complete(completed_dates, training_weekdays, frozen_dates, today=None) -> bool:
    """True when every scheduled training day of today's ISO week with
    date <= today is completed or frozen (used to earn a freeze)."""
    if today is None:
        today = date.today()
    else:
        today = _parse(today)

    training = set(training_weekdays)
    if not training:
        return False
    done = {_parse(d) for d in completed_dates}
    frozen = {_parse(d) for d in frozen_dates}

    monday = today - timedelta(days=today.weekday())
    scheduled = [monday + timedelta(days=i) for i in range(7)
                 if (monday + timedelta(days=i)).weekday() in training
                 and monday + timedelta(days=i) <= today]
    if not scheduled:
        return False
    return all(d in done or d in frozen for d in scheduled)
