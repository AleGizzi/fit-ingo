"""Wearable data import — Garmin/fit-band ``.FIT`` files, fully local.

No Garmin Connect account or cloud API involved: the user exports/copies the
``.FIT`` files a watch or band records (activities and daily "monitoring"
wellness files) and uploads them in the app. We parse them with ``fitdecode``
(pure Python, runs in Termux) and keep two views:

- **activities** — one row per workout session (sport, duration, distance,
  avg/max heart rate, calories).
- **health_daily** — one row per calendar day (steps, resting HR, calories)
  merged from monitoring files.

``aggregate()`` is separated from file decoding so the mapping logic is
testable without crafting binary FIT fixtures.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import fitdecode

# Wellness/monitoring FIT files count steps cumulatively during the day per
# activity type; the day's total is the max cumulative value seen per date.


def parse_fit_bytes(data: bytes, filename: str = "upload.fit") -> dict:
    """Decode one .FIT file into {activities:[…], daily:{date:{…}}}.

    Raises ValueError on files fitdecode can't read (wrong format/corrupt).
    """
    records: list[dict] = []
    try:
        with fitdecode.FitReader(io.BytesIO(data)) as reader:
            for frame in reader:
                if isinstance(frame, fitdecode.FitDataMessage):
                    records.append({
                        "name": frame.name,
                        "fields": {f.name: f.value for f in frame.fields},
                    })
    except Exception as exc:
        raise ValueError(f"not a valid FIT file: {exc}") from exc
    return aggregate(records, filename)


def aggregate(records: list[dict], filename: str) -> dict:
    """Map decoded FIT messages onto our storage shapes (pure function)."""
    activities: list[dict] = []
    daily: dict[str, dict] = {}

    def day_bucket(d: str) -> dict:
        return daily.setdefault(
            d, {"steps": None, "resting_hr": None, "calories": None})

    for rec in records:
        fields = rec["fields"]

        if rec["name"] == "session":
            start = _ts(fields.get("start_time") or fields.get("timestamp"))
            if not start:
                continue
            dur = fields.get("total_elapsed_time")
            dist = fields.get("total_distance")
            activities.append({
                "start_ts": start.isoformat(),
                "sport": str(fields.get("sport") or "unknown"),
                "duration_min": round(dur / 60, 1) if dur else None,
                "distance_km": round(dist / 1000, 2) if dist else None,
                "avg_hr": _int(fields.get("avg_heart_rate")),
                "max_hr": _int(fields.get("max_heart_rate")),
                "calories": _int(fields.get("total_calories")),
                "source_file": filename,
            })

        elif rec["name"] == "monitoring":
            ts = _ts(fields.get("timestamp"))
            if not ts:
                continue
            bucket = day_bucket(ts.date().isoformat())
            steps = _int(fields.get("steps"))
            if steps is not None:
                bucket["steps"] = max(bucket["steps"] or 0, steps)
            cals = _int(fields.get("active_calories"))
            if cals is not None:
                bucket["calories"] = max(bucket["calories"] or 0, cals)

        elif rec["name"] in ("monitoring_hr_data", "monitoring_info"):
            ts = _ts(fields.get("timestamp"))
            rhr = _int(fields.get("resting_heart_rate"))
            if ts and rhr:
                day_bucket(ts.date().isoformat())["resting_hr"] = rhr

    # Wellness files without explicit resting HR: some devices put it on the
    # session-less "stress_level"/"hr" stream — skipped on purpose; we only
    # report values the device itself called resting HR.
    return {"activities": activities, "daily": daily}


def _ts(value) -> datetime | None:
    if isinstance(value, datetime):
        # FIT timestamps are UTC; normalize aware→naive local-agnostic ISO.
        return value.astimezone(timezone.utc) if value.tzinfo else value
    return None


def _int(value) -> int | None:
    try:
        if value is None:
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
