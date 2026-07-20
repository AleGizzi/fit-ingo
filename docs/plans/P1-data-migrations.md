# P1 — Schema v3 + data contracts (blocks P2, P5, P7, P9)

**Model: sonnet · Backend only · No UI**

## Objective

One migration that carries every downstream packet's storage, so later
packets never touch the schema. Also normalize the `items_done` log format
(tech debt).

## Files touched

- `server/db.py` (schema, migration, helpers)
- `server/tests/test_migrations.py` (new)
- `server/tests/test_water_health.py` (extend the v1-migration test's pattern)

## Current state

- `SCHEMA_VERSION = 2` in `server/db.py`; `_migrate(conn, from_version)`
  handles v1→v2 (water columns) via `PRAGMA table_info` guards.
- `workout_log.items_done` holds a JSON array of strings. Modern entries are
  `"<exercise_id>:<block>:<position>"` (see `itemKey()` in
  `frontend/src/pages/Workout.tsx`); entries logged before ~v1.1 may be bare
  `"<exercise_id>"`. Nothing normalizes them.

## Changes (frozen contract — downstream packets rely on these exact names)

### 1. Schema v3

Bump `SCHEMA_VERSION` to 3. New DDL in `_init_schema` **and** matching
`_migrate` branch (`if from_version < 3:` with `PRAGMA table_info` /
`CREATE TABLE IF NOT EXISTS` guards):

```sql
-- streak freezes (P2). Activity state, not preference.
CREATE TABLE IF NOT EXISTS streak_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    freezes INTEGER NOT NULL DEFAULT 0,        -- banked, 0..2
    frozen_dates TEXT NOT NULL DEFAULT '[]',   -- JSON [YYYY-MM-DD] consumed
    last_earned_week TEXT                      -- ISO week 'YYYY-Www' guard
);
```

`ALTER TABLE` additions:

| Table | Column | Type/default | For |
|---|---|---|---|
| `workout_log` | `avg_hr` | `INTEGER` (null) | P9 |
| `workout_log` | `max_hr` | `INTEGER` (null) | P9 |
| `settings` | `weekly_recap_enabled` | `INTEGER DEFAULT 1` | P7 |
| `settings` | `excluded_exercises` | `TEXT DEFAULT '[]'` (JSON ids) | P5 |

Insert `INSERT OR IGNORE INTO streak_state(id) VALUES (1)` next to the
existing settings singleton insert.

### 2. Helpers (add to db.py)

```python
def get_streak_state() -> dict      # {"freezes": int, "frozen_dates": [str], "last_earned_week": str|None}
def save_streak_state(freezes: int, frozen_dates: list[str], last_earned_week: str | None) -> None
def get_excluded_exercises() -> list[str]
def set_excluded_exercises(ids: list[str]) -> None
```

JSON columns decode on read like `get_settings()` does. Writes under
`with _lock:`.

### 3. Wire into lifecycle

- `get_settings()`: decode `excluded_exercises` to a list,
  `weekly_recap_enabled` to bool (mirror existing bool/JSON handling).
- `clear_activity()`: also reset `streak_state` (freezes are earned by
  activity, so they wipe with it): `UPDATE streak_state SET freezes=0,
  frozen_dates='[]', last_earned_week=NULL WHERE id=1`.
  **Do not** clear `excluded_exercises` (a disliked exercise stays disliked).
- `reset_all()`: delete + re-insert `streak_state` row; settings reset
  already covers the new columns.

### 4. items_done normalization (tech debt)

Add to db.py:

```python
def normalize_item_keys(items_done: list[str]) -> list[str]:
    """Log format v2: every entry is 'exercise_id:block:position'.
    Legacy bare ids become 'id:main:<index>' so old logs stay renderable."""
```

Call it in `app.py`'s `log_workout()` before storing. P4 (history rendering)
consumes this format; document it in the function docstring.

## Out of scope

Any use of the new storage (that's P2/P5/P7/P9). No API changes beyond the
`log_workout` normalization call. No frontend.

## Verify

```bash
cd server && ../.venv/bin/python -m pytest -q          # all green
```

New tests must cover:
- v2 DB (build one in-test like `test_v1_db_migrates_in_place` does)
  migrates to v3 keeping settings + water rows; `streak_state` row exists.
- Fresh DB creates everything at v3 directly.
- `clear_activity()` zeroes streak_state but keeps `excluded_exercises`.
- `normalize_item_keys(["push-up", "squat:main:2"])` →
  `["push-up:main:0", "squat:main:2"]`.
- Round-trip of all four new helpers.

## Acceptance

All the above tests green; existing 56 tests untouched and green; no other
behavior change observable via the API.
