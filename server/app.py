"""Fit-ingo Flask server.

Serves the built PWA (``frontend/dist``) plus a small JSON API, and runs the
reminder scheduler thread. Local-only, single-user, no auth.

Run:  python app.py            (serves on 0.0.0.0:8777)
Env:  FITINGO_DB   override the SQLite path
      FITINGO_PORT override the port (default 8777)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import db
import diet as diet_engine
import planner as planner_engine
import health as health_engine
import quick as quick_engine
from reminders import ReminderScheduler, get_status, send_notification
from streak import compute_streak, consume_freezes, week_complete

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fitingo")

HERE = Path(__file__).resolve().parent
DIST = HERE.parent / "frontend" / "dist"

app = Flask(__name__, static_folder=None)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _today_iso() -> str:
    return date.today().isoformat()


def active_plan_id(conn) -> int | None:
    row = conn.execute("SELECT id FROM plan WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def training_weekdays() -> list[int]:
    """Weekdays (0=Mon) that are training days in the active plan."""
    conn = db.get_conn()
    pid = active_plan_id(conn)
    if pid is None:
        return []
    rows = conn.execute(
        "SELECT weekday FROM plan_days WHERE plan_id=? AND is_rest=0", (pid,)
    ).fetchall()
    return [r["weekday"] for r in rows]


def is_today_done() -> bool:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT completed FROM workout_log WHERE date=?", (_today_iso(),)
    ).fetchone()
    return bool(row and row["completed"])


def completed_dates() -> list[str]:
    conn = db.get_conn()
    rows = conn.execute("SELECT date FROM workout_log WHERE completed=1").fetchall()
    return [r["date"] for r in rows]


def _save_plan(days: list[planner_engine.PlanDay], profile: dict, week: int = 1) -> int:
    """Persist a generated plan, deactivating any previous one. Returns plan id."""
    conn = db.get_conn()
    with db._lock:
        conn.execute("UPDATE plan SET active=0 WHERE active=1")
        cur = conn.execute(
            "INSERT INTO plan(week, active, meta) VALUES (?,1,?)",
            (week, json.dumps({"goal": profile.get("goal"), "level": profile.get("level")})),
        )
        plan_id = cur.lastrowid
        for day in days:
            dcur = conn.execute(
                "INSERT INTO plan_days(plan_id, weekday, is_rest, focus) VALUES (?,?,?,?)",
                (plan_id, day.weekday, int(day.is_rest), day.focus),
            )
            day_id = dcur.lastrowid
            for pos, it in enumerate(day.items):
                conn.execute(
                    """INSERT INTO plan_items
                       (plan_day_id, exercise_id, position, block, sets, reps, duration_sec, rest_sec)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (day_id, it.exercise_id, pos, it.block, it.sets, it.reps,
                     it.duration_sec, it.rest_sec),
                )
        conn.commit()
    return plan_id


def _plan_to_json(plan_id: int) -> dict:
    conn = db.get_conn()
    plan = conn.execute("SELECT * FROM plan WHERE id=?", (plan_id,)).fetchone()
    days = conn.execute(
        "SELECT * FROM plan_days WHERE plan_id=? ORDER BY weekday", (plan_id,)
    ).fetchall()
    out_days = []
    for d in days:
        items = conn.execute(
            "SELECT * FROM plan_items WHERE plan_day_id=? ORDER BY position", (d["id"],)
        ).fetchall()
        out_days.append({
            "weekday": d["weekday"],
            "is_rest": bool(d["is_rest"]),
            "focus": d["focus"],
            "items": [dict(i) for i in items],
        })
    return {
        "id": plan_id,
        "week": plan["week"],
        "meta": json.loads(plan["meta"] or "{}"),
        "days": out_days,
    }


def _regenerate_for_profile(profile: dict, week: int = 1) -> int:
    exercises = db.all_exercises()
    days = planner_engine.generate_plan(exercises, profile, seed=None)
    return _save_plan(days, profile, week=week)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_unexpected(e):
    """Always return JSON (not an HTML 500) so the PWA can surface the real
    error to the user instead of failing silently."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    log.exception("Unhandled error on %s", request.path)
    return jsonify({"error": str(e) or e.__class__.__name__}), 500


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "time": datetime.now().isoformat()})


@app.get("/api/profile")
def get_profile():
    return jsonify(db.get_profile())


@app.post("/api/profile")
def save_profile():
    p = request.get_json(force=True) or {}
    conn = db.get_conn()
    fields = ["name", "age", "sex", "height_cm", "weight_kg", "goal", "level",
              "impact", "equipment", "days_per_week", "session_minutes", "diet_pref"]
    values = {k: p.get(k) for k in fields}
    values["limitations"] = json.dumps(p.get("limitations") or [])
    with db._lock:
        existing = conn.execute("SELECT id FROM profile WHERE id=1").fetchone()
        cols = fields + ["limitations"]
        if existing:
            sets = ", ".join(f"{c}=?" for c in cols) + ", updated_at=datetime('now')"
            conn.execute(f"UPDATE profile SET {sets} WHERE id=1",
                         [values[c] for c in cols])
        else:
            placeholders = ", ".join("?" for _ in cols)
            conn.execute(
                f"INSERT INTO profile(id, {', '.join(cols)}) VALUES (1, {placeholders})",
                [values[c] for c in cols],
            )
        conn.commit()

    # Changing the profile invalidates the current plan's history: wipe
    # workout/weight logs so the streak and charts start clean, then
    # (re)generate the plan whenever the profile changes.
    db.clear_activity()
    profile = db.get_profile()
    plan_id = _regenerate_for_profile(profile)
    return jsonify({"profile": profile, "plan": _plan_to_json(plan_id)})


@app.get("/api/exercises")
def get_exercises():
    return jsonify(db.all_exercises())


@app.patch("/api/exercises/<eid>")
def update_exercise(eid):
    """Only the video URL is user-editable (fix dead links)."""
    body = request.get_json(force=True) or {}
    url = body.get("video_url")
    if not url:
        return jsonify({"error": "video_url required"}), 400
    conn = db.get_conn()
    with db._lock:
        conn.execute("UPDATE exercises SET video_url=? WHERE id=?", (url, eid))
        conn.commit()
    return jsonify({"ok": True})


@app.get("/api/plan")
def get_plan():
    conn = db.get_conn()
    pid = active_plan_id(conn)
    if pid is None:
        return jsonify(None)
    return jsonify(_plan_to_json(pid))


@app.post("/api/plan/regenerate")
def regenerate_plan():
    profile = db.get_profile()
    if not profile:
        return jsonify({"error": "no profile"}), 400
    # Weekly progression: look at last week's completion to scale the new plan.
    factor = _last_week_progression()
    exercises = db.all_exercises()
    days = planner_engine.generate_plan(exercises, profile)
    days = planner_engine.apply_progression(days, factor)
    conn = db.get_conn()
    prev = conn.execute("SELECT week FROM plan WHERE active=1").fetchone()
    week = (prev["week"] + 1) if prev else 1
    pid = _save_plan(days, profile, week=week)
    return jsonify({"plan": _plan_to_json(pid), "progression_factor": factor})


def _last_week_progression() -> float:
    """Compute a progression multiplier from the last 7 days of logs."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT completed, perceived_difficulty FROM workout_log "
        "WHERE date >= date('now','-7 day')"
    ).fetchall()
    tdays = len(training_weekdays()) or 3
    done = sum(1 for r in rows if r["completed"])
    completion = min(1.0, done / tdays) if tdays else 0.0
    diffs = [r["perceived_difficulty"] for r in rows if r["perceived_difficulty"] is not None]
    avg_diff = sum(diffs) / len(diffs) if diffs else 3.0
    return planner_engine.progression_factor(completion, avg_diff)


@app.get("/api/quick/<kind>")
def get_quick(kind):
    """A bonus mini-session (quick 10' workout / desk break / wellness flow).
    Generated fresh each call; nothing is persisted and the streak is not
    involved — these live besides the weekly goal."""
    if kind not in quick_engine.KINDS:
        return jsonify({"error": f"unknown kind: {kind}"}), 404
    session = quick_engine.build_session(db.all_exercises(), db.get_profile(), kind)
    return jsonify(session)


@app.get("/api/today")
def get_today():
    """The plan day for today + its completion state."""
    conn = db.get_conn()
    pid = active_plan_id(conn)
    wd = date.today().weekday()
    day = None
    if pid is not None:
        drow = conn.execute(
            "SELECT * FROM plan_days WHERE plan_id=? AND weekday=?", (pid, wd)
        ).fetchone()
        if drow:
            items = conn.execute(
                "SELECT * FROM plan_items WHERE plan_day_id=? ORDER BY position", (drow["id"],)
            ).fetchall()
            day = {
                "weekday": wd,
                "is_rest": bool(drow["is_rest"]),
                "focus": drow["focus"],
                "items": [dict(i) for i in items],
            }
    logrow = conn.execute("SELECT * FROM workout_log WHERE date=?", (_today_iso(),)).fetchone()
    return jsonify({
        "date": _today_iso(),
        "weekday": wd,
        "day": day,
        "log": dict(logrow) if logrow else None,
    })


@app.post("/api/log")
def log_workout():
    """Record (or update) today's workout completion.

    Body: { items_done: [ids], items_total, completed: bool,
            perceived_difficulty: 1..5, duration_min }
    """
    body = request.get_json(force=True) or {}
    d = body.get("date") or _today_iso()
    conn = db.get_conn()
    pid = active_plan_id(conn)
    items_done = db.normalize_item_keys(body.get("items_done") or [])
    payload = (
        d, pid, int(bool(body.get("completed"))), json.dumps(items_done),
        body.get("items_total"), body.get("perceived_difficulty"),
        body.get("duration_min"),
    )
    with db._lock:
        conn.execute(
            """INSERT INTO workout_log
               (date, plan_id, completed, items_done, items_total, perceived_difficulty, duration_min)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 plan_id=excluded.plan_id,
                 completed=excluded.completed,
                 items_done=excluded.items_done,
                 items_total=excluded.items_total,
                 perceived_difficulty=excluded.perceived_difficulty,
                 duration_min=excluded.duration_min""",
            payload,
        )
        conn.commit()

    earned = bool(body.get("completed")) and _maybe_earn_freeze()
    return jsonify({"ok": True, "streak": _streak(), "freeze_earned": earned})


def _streak() -> dict:
    """Streak with lazy freeze consumption: any missed-day gap that banked
    freezes can bridge is frozen (persisted) the first time anyone looks."""
    state = db.get_streak_state()
    done = completed_dates()
    tw = training_weekdays()
    freezes, frozen, changed = consume_freezes(
        done, tw, state["freezes"], state["frozen_dates"])
    if changed:
        db.save_streak_state(freezes, frozen, state["last_earned_week"])
    s = compute_streak(done, tw, frozen_dates=frozen)
    s["freezes"] = freezes
    s["frozen_dates"] = frozen
    return s


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _maybe_earn_freeze() -> bool:
    """+1 freeze (cap 2) when this ISO week's schedule is fully covered.
    At most one earn per week. Called after a completed workout is saved."""
    state = db.get_streak_state()
    week = _iso_week(date.today())
    if state["last_earned_week"] == week or state["freezes"] >= 2:
        return False
    if not week_complete(completed_dates(), training_weekdays(),
                         state["frozen_dates"]):
        return False
    db.save_streak_state(state["freezes"] + 1, state["frozen_dates"], week)
    return True


@app.get("/api/streak")
def get_streak():
    return jsonify(_streak())


@app.get("/api/metrics")
def get_metrics():
    """Progress data for charts: weight history, completion history, streak."""
    conn = db.get_conn()
    weights = [dict(r) for r in conn.execute(
        "SELECT date, weight_kg FROM weight_log ORDER BY date").fetchall()]
    logs = [dict(r) for r in conn.execute(
        "SELECT date, completed, items_total, perceived_difficulty, duration_min "
        "FROM workout_log ORDER BY date").fetchall()]
    total = len(logs)
    completed = sum(1 for l in logs if l["completed"])
    return jsonify({
        "weights": weights,
        "logs": logs,
        "streak": _streak(),
        "totals": {
            "workouts_completed": completed,
            "workouts_logged": total,
            "completion_rate": round(completed / total, 2) if total else 0,
        },
    })


@app.post("/api/weight")
def log_weight():
    body = request.get_json(force=True) or {}
    w = body.get("weight_kg")
    d = body.get("date") or _today_iso()
    if w is None:
        return jsonify({"error": "weight_kg required"}), 400
    conn = db.get_conn()
    with db._lock:
        conn.execute(
            "INSERT INTO weight_log(date, weight_kg) VALUES (?,?) "
            "ON CONFLICT(date) DO UPDATE SET weight_kg=excluded.weight_kg",
            (d, float(w)),
        )
        conn.commit()
    return jsonify({"ok": True})


@app.get("/api/diet")
def get_diet():
    profile = db.get_profile()
    if not profile:
        return jsonify({"error": "no profile"}), 400
    t = diet_engine.targets(profile)
    suggestions = diet_engine.suggest_meals(profile, t["kcal"])
    return jsonify({"targets": t, "suggestions": suggestions})


@app.get("/api/water")
def get_water():
    day = request.args.get("date") or _today_iso()
    settings = db.get_settings()
    return jsonify({
        "date": day,
        "ml": db.get_water(day),
        "goal_ml": settings["water_goal_ml"],
        "history": db.water_history(14),
    })


@app.post("/api/water")
def log_water():
    """Add (or, with a negative delta, undo) a drink for today."""
    body = request.get_json(force=True) or {}
    delta = int(body.get("delta_ml") or 0)
    day = body.get("date") or _today_iso()
    ml = db.add_water(day, delta)
    return jsonify({"date": day, "ml": ml,
                    "goal_ml": db.get_settings()["water_goal_ml"]})


@app.post("/api/health/import")
def health_import():
    """Import wearable .FIT files (multipart form, field name 'files')."""
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400
    new_activities = 0
    days_updated: set[str] = set()
    errors: list[str] = []
    for f in files:
        try:
            parsed = health_engine.parse_fit_bytes(f.read(), f.filename or "upload.fit")
        except ValueError as exc:
            errors.append(f"{f.filename}: {exc}")
            continue
        for act in parsed["activities"]:
            if db.insert_activity(act):
                new_activities += 1
        for day, vals in parsed["daily"].items():
            db.upsert_health_daily(day, vals["steps"], vals["resting_hr"],
                                   vals["calories"], f.filename or "upload.fit")
            days_updated.add(day)
    return jsonify({
        "activities_imported": new_activities,
        "days_updated": len(days_updated),
        "errors": errors,
    })


@app.get("/api/health/summary")
def health_summary():
    return jsonify(db.health_summary())


@app.get("/api/settings")
def get_settings():
    return jsonify(db.get_settings())


@app.post("/api/settings")
def save_settings():
    body = request.get_json(force=True) or {}
    conn = db.get_conn()
    cur = db.get_settings()
    lang = body.get("language", cur["language"])
    theme = body.get("theme", cur["theme"])
    rem_en = int(bool(body.get("reminder_enabled", cur["reminder_enabled"])))
    rem_times = json.dumps(body.get("reminder_times", cur["reminder_times"]))
    nag_en = int(bool(body.get("nag_enabled", cur["nag_enabled"])))
    nag_time = body.get("nag_time", cur["nag_time"])
    water_goal = int(body.get("water_goal_ml", cur["water_goal_ml"]))
    water_en = int(bool(body.get("water_reminder_enabled", cur["water_reminder_enabled"])))
    water_int = int(body.get("water_interval_min", cur["water_interval_min"]))
    water_start = body.get("water_start", cur["water_start"])
    water_end = body.get("water_end", cur["water_end"])
    with db._lock:
        conn.execute(
            """UPDATE settings SET language=?, theme=?, reminder_enabled=?,
               reminder_times=?, nag_enabled=?, nag_time=?,
               water_goal_ml=?, water_reminder_enabled=?, water_interval_min=?,
               water_start=?, water_end=? WHERE id=1""",
            (lang, theme, rem_en, rem_times, nag_en, nag_time,
             water_goal, water_en, water_int, water_start, water_end),
        )
        conn.commit()
    return jsonify(db.get_settings())


@app.get("/api/notifications/status")
def notifications_status():
    return jsonify(get_status())


@app.post("/api/notifications/test")
def notifications_test():
    result = send_notification("Fit-ingo", "Test notification ✅")
    return jsonify(result)


@app.post("/api/reset")
def reset():
    """Factory reset: wipe profile, plan and history. Exercise catalog stays."""
    db.reset_all()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Static PWA serving (SPA fallback)
# --------------------------------------------------------------------------

@app.get("/")
@app.get("/<path:path>")
def serve_spa(path: str = ""):
    if not DIST.exists():
        return (
            "<h1>Fit-ingo</h1><p>Frontend not built yet. "
            "Run <code>npm run build</code> in <code>frontend/</code>.</p>",
            200,
        )
    target = DIST / path
    if path and target.is_file():
        return send_from_directory(DIST, path)
    return send_from_directory(DIST, "index.html")


# --------------------------------------------------------------------------
# Boot
# --------------------------------------------------------------------------

def _water_today() -> tuple[int, int]:
    return db.get_water(_today_iso()), db.get_settings()["water_goal_ml"]


scheduler = ReminderScheduler(
    get_settings=db.get_settings,
    get_training_weekdays=training_weekdays,
    is_today_done=is_today_done,
    get_water_today=_water_today,
)


def create_app() -> Flask:
    db.get_conn()          # ensure schema + seed
    scheduler.start()
    return app


if __name__ == "__main__":
    create_app()
    port = int(os.environ.get("FITINGO_PORT", "8777"))
    app.run(host="0.0.0.0", port=port, threaded=True)
