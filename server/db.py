"""SQLite storage for Fit-ingo.

Single-user, local-only. The database lives next to the process by default
(``server/data/fitingo.db``) but the path is overridable via the
``FITINGO_DB`` environment variable so Termux can point it at
``~/fit-ingo/data/fitingo.db``.

The schema is created idempotently and the exercise catalog is seeded from
``seed/exercises.json`` on first run. A tiny ``schema_version`` row lets us add
migrations later without clobbering user data.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED_DIR = HERE / "seed"

DEFAULT_DB = HERE / "data" / "fitingo.db"
SCHEMA_VERSION = 2

# One connection *per thread*. Flask serves threaded and the reminder thread
# touches the DB too; sharing a single connection across them interleaves
# execute/fetch on the same cursor, which intermittently yields a phantom empty
# result (`dict(None)` -> TypeError) on perfectly good data. WAL gives us
# concurrent readers plus one writer, which is exactly this workload, and
# `_lock` still serializes our own multi-statement writes.
_local = threading.local()
_schema_ready = False
_lock = threading.RLock()


def db_path() -> Path:
    return Path(os.environ.get("FITINGO_DB", str(DEFAULT_DB)))


def get_conn() -> sqlite3.Connection:
    global _schema_ready
    conn = getattr(_local, "conn", None)
    if conn is None:
        path = db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # timeout: wait out a concurrent writer instead of raising "database
        # is locked" — writes here are tiny, so this should never be hit.
        conn = sqlite3.connect(str(path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        with _lock:
            if not _schema_ready:
                _init_schema(conn)
                _schema_ready = True
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    with _lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                age INTEGER,
                sex TEXT,
                height_cm REAL,
                weight_kg REAL,
                goal TEXT,
                level TEXT,
                impact TEXT,
                equipment TEXT,
                days_per_week INTEGER,
                session_minutes INTEGER,
                limitations TEXT,          -- JSON array
                diet_pref TEXT,            -- 'any' | 'vegetarian'
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS exercises (
                id TEXT PRIMARY KEY,
                name_en TEXT, name_es TEXT,
                instructions_en TEXT, instructions_es TEXT,
                video_url TEXT,
                muscle_groups TEXT,        -- JSON array
                type TEXT,
                impact TEXT,
                difficulty INTEGER,
                equipment TEXT,
                contraindications TEXT     -- JSON array
            );

            CREATE TABLE IF NOT EXISTS plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                week INTEGER DEFAULT 1,
                active INTEGER DEFAULT 1,
                meta TEXT                   -- JSON: goal snapshot etc.
            );

            -- One row per (plan, weekday). weekday 0=Mon .. 6=Sun.
            CREATE TABLE IF NOT EXISTS plan_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL REFERENCES plan(id) ON DELETE CASCADE,
                weekday INTEGER NOT NULL,
                is_rest INTEGER DEFAULT 0,
                focus TEXT
            );

            CREATE TABLE IF NOT EXISTS plan_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_day_id INTEGER NOT NULL REFERENCES plan_days(id) ON DELETE CASCADE,
                exercise_id TEXT NOT NULL,
                position INTEGER,
                block TEXT,                 -- warmup | main | cooldown
                sets INTEGER,
                reps INTEGER,               -- null when duration-based
                duration_sec INTEGER,       -- null when rep-based
                rest_sec INTEGER
            );

            -- One row per completed (or attempted) workout day.
            CREATE TABLE IF NOT EXISTS workout_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,         -- YYYY-MM-DD (local)
                plan_id INTEGER,
                completed INTEGER DEFAULT 0,
                items_done TEXT,            -- JSON array of exercise ids done
                items_total INTEGER,
                perceived_difficulty REAL,  -- 1..5 avg
                duration_min INTEGER,
                UNIQUE(date)
            );

            CREATE TABLE IF NOT EXISTS weight_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                weight_kg REAL NOT NULL,
                UNIQUE(date)
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                language TEXT DEFAULT 'en',
                theme TEXT DEFAULT 'system',
                reminder_enabled INTEGER DEFAULT 1,
                reminder_times TEXT DEFAULT '["18:00"]',  -- JSON array HH:MM
                nag_enabled INTEGER DEFAULT 1,
                nag_time TEXT DEFAULT '21:00',
                water_goal_ml INTEGER DEFAULT 2000,
                water_reminder_enabled INTEGER DEFAULT 0,
                water_interval_min INTEGER DEFAULT 120,
                water_start TEXT DEFAULT '09:00',
                water_end TEXT DEFAULT '21:00'
            );

            -- One row per date; ml accumulates through the day.
            CREATE TABLE IF NOT EXISTS water_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ml INTEGER NOT NULL DEFAULT 0,
                UNIQUE(date)
            );

            -- Imported wearable data (Garmin/fit band .FIT files).
            CREATE TABLE IF NOT EXISTS health_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                steps INTEGER,
                resting_hr INTEGER,
                calories INTEGER,
                source TEXT,
                UNIQUE(date)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts TEXT NOT NULL,     -- ISO datetime, dedup key
                sport TEXT,
                duration_min REAL,
                distance_km REAL,
                avg_hr INTEGER,
                max_hr INTEGER,
                calories INTEGER,
                source_file TEXT,
                UNIQUE(start_ts)
            );
            """
        )
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        else:
            _migrate(conn, int(row["value"]))
        conn.execute("INSERT OR IGNORE INTO settings(id) VALUES (1)")
        conn.commit()
        _seed_exercises(conn)


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    """Bring an existing DB up to SCHEMA_VERSION without touching user data.
    New tables are already covered by CREATE IF NOT EXISTS above; this only
    handles ALTERs that executescript can't express idempotently."""
    if from_version < 2:
        # v2: water tracking columns on settings.
        have = {r["name"] for r in conn.execute("PRAGMA table_info(settings)")}
        for col, ddl in [
            ("water_goal_ml", "INTEGER DEFAULT 2000"),
            ("water_reminder_enabled", "INTEGER DEFAULT 0"),
            ("water_interval_min", "INTEGER DEFAULT 120"),
            ("water_start", "TEXT DEFAULT '09:00'"),
            ("water_end", "TEXT DEFAULT '21:00'"),
        ]:
            if col not in have:
                conn.execute(f"ALTER TABLE settings ADD COLUMN {col} {ddl}")
    if from_version != SCHEMA_VERSION:
        conn.execute(
            "UPDATE meta SET value=? WHERE key='schema_version'",
            (str(SCHEMA_VERSION),),
        )


def _seed_exercises(conn: sqlite3.Connection) -> None:
    """Load the catalog once. Existing rows (with user-edited video URLs) are
    preserved; only genuinely new exercise ids are inserted."""
    seed_file = SEED_DIR / "exercises.json"
    if not seed_file.exists():
        return
    data = json.loads(seed_file.read_text(encoding="utf-8"))
    existing = {r["id"] for r in conn.execute("SELECT id FROM exercises")}
    to_add = [e for e in data if e["id"] not in existing]
    for e in to_add:
        conn.execute(
            """INSERT INTO exercises
               (id, name_en, name_es, instructions_en, instructions_es, video_url,
                muscle_groups, type, impact, difficulty, equipment, contraindications)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                e["id"], e["name_en"], e["name_es"],
                e["instructions_en"], e["instructions_es"], e["video_url"],
                json.dumps(e["muscle_groups"]), e["type"], e["impact"],
                e["difficulty"], e["equipment"], json.dumps(e["contraindications"]),
            ),
        )
    if to_add:
        conn.commit()


# ---- convenience row -> dict helpers -------------------------------------

def exercise_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name_en": row["name_en"],
        "name_es": row["name_es"],
        "instructions_en": row["instructions_en"],
        "instructions_es": row["instructions_es"],
        "video_url": row["video_url"],
        "muscle_groups": json.loads(row["muscle_groups"] or "[]"),
        "type": row["type"],
        "impact": row["impact"],
        "difficulty": row["difficulty"],
        "equipment": row["equipment"],
        "contraindications": json.loads(row["contraindications"] or "[]"),
    }


def all_exercises() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM exercises ORDER BY type, difficulty").fetchall()
    return [exercise_to_dict(r) for r in rows]


def get_profile() -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    if not row:
        return None
    d = dict(row)
    d["limitations"] = json.loads(d.get("limitations") or "[]")
    return d


def get_settings() -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
    if row is None:
        # Only reachable if the singleton row was lost (an interrupted reset);
        # recreate the defaults rather than 500 on every request from then on.
        with _lock:
            conn.execute("INSERT OR IGNORE INTO settings(id) VALUES (1)")
            conn.commit()
        row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
    d = dict(row)
    d["reminder_times"] = json.loads(d.get("reminder_times") or "[]")
    d["reminder_enabled"] = bool(d["reminder_enabled"])
    d["nag_enabled"] = bool(d["nag_enabled"])
    d["water_reminder_enabled"] = bool(d["water_reminder_enabled"])
    return d


def get_water(day: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT ml FROM water_log WHERE date=?", (day,)).fetchone()
    return row["ml"] if row else 0


def add_water(day: str, delta_ml: int) -> int:
    """Accumulate today's intake; clamps at 0 so undo can't go negative."""
    conn = get_conn()
    with _lock:
        conn.execute(
            """INSERT INTO water_log(date, ml) VALUES (?, MAX(0, ?))
               ON CONFLICT(date) DO UPDATE SET ml = MAX(0, ml + ?)""",
            (day, delta_ml, delta_ml),
        )
        conn.commit()
    return get_water(day)


def water_history(days: int = 30) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT date, ml FROM water_log ORDER BY date DESC LIMIT ?", (days,)
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def upsert_health_daily(day: str, steps: int | None, resting_hr: int | None,
                        calories: int | None, source: str) -> None:
    """Merge a day's wearable summary; newer non-null values win."""
    conn = get_conn()
    with _lock:
        conn.execute(
            """INSERT INTO health_daily(date, steps, resting_hr, calories, source)
               VALUES (?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 steps      = COALESCE(excluded.steps, steps),
                 resting_hr = COALESCE(excluded.resting_hr, resting_hr),
                 calories   = COALESCE(excluded.calories, calories),
                 source     = excluded.source""",
            (day, steps, resting_hr, calories, source),
        )
        conn.commit()


def insert_activity(a: dict) -> bool:
    """Insert an imported activity; returns False if already imported
    (same start timestamp)."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            """INSERT OR IGNORE INTO activities
               (start_ts, sport, duration_min, distance_km, avg_hr, max_hr,
                calories, source_file)
               VALUES (?,?,?,?,?,?,?,?)""",
            (a["start_ts"], a.get("sport"), a.get("duration_min"),
             a.get("distance_km"), a.get("avg_hr"), a.get("max_hr"),
             a.get("calories"), a.get("source_file")),
        )
        conn.commit()
    return cur.rowcount > 0


def health_summary(days: int = 90) -> dict:
    conn = get_conn()
    daily = conn.execute(
        "SELECT date, steps, resting_hr, calories FROM health_daily "
        "ORDER BY date DESC LIMIT ?", (days,)
    ).fetchall()
    acts = conn.execute(
        "SELECT * FROM activities ORDER BY start_ts DESC LIMIT 20"
    ).fetchall()
    return {
        "daily": [dict(r) for r in reversed(daily)],
        "activities": [dict(r) for r in acts],
    }


def clear_activity() -> None:
    """Wipe workout/weight/water history (used when the profile changes so the
    streak and progress charts start clean for the new plan). Imported
    wearable data is device truth, not plan progress — it survives."""
    conn = get_conn()
    with _lock:
        conn.execute("DELETE FROM workout_log")
        conn.execute("DELETE FROM weight_log")
        conn.execute("DELETE FROM water_log")
        conn.commit()


def reset_all() -> None:
    """Factory reset: wipe profile, plan and all activity, and restore
    default settings. The exercise catalog is left untouched."""
    conn = get_conn()
    with _lock:
        conn.execute("DELETE FROM profile")
        conn.execute("DELETE FROM plan_items")
        conn.execute("DELETE FROM plan_days")
        conn.execute("DELETE FROM plan")
        conn.execute("DELETE FROM workout_log")
        conn.execute("DELETE FROM weight_log")
        conn.execute("DELETE FROM water_log")
        conn.execute("DELETE FROM health_daily")
        conn.execute("DELETE FROM activities")
        conn.execute("DELETE FROM settings")
        conn.execute("INSERT OR IGNORE INTO settings(id) VALUES (1)")
        conn.commit()
