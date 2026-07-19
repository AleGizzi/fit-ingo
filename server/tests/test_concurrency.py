"""The API is served threaded and the reminder thread touches the DB too, so
every endpoint has to survive concurrent access.

Regression test for a shared-connection bug: db.get_conn() used to hand the
same sqlite3 connection to every thread, so one thread's execute() could reset
the cursor another thread was still fetching from. Reads then returned a
phantom None on perfectly good data and the request 500'd
("'NoneType' object is not iterable"). It reproduced at roughly 2% of requests
here, which on-device looked like random silent failures when saving a profile
or logging a workout.
"""

import sys
import threading
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FITINGO_DB", str(tmp_path / "concurrency.db"))
    # Import late so the env var is in place, and reset the module's cached
    # per-thread connections/schema flag between tests.
    import db

    db._local = threading.local()
    db._schema_ready = False
    import app as app_module

    db.get_conn()
    return app_module.app.test_client()


PROFILE = {
    "name": "T", "age": 30, "sex": "male", "height_cm": 170, "weight_kg": 75,
    "goal": "maintain", "level": "beginner", "impact": "low", "equipment": "none",
    "days_per_week": 3, "session_minutes": 30, "limitations": [], "diet_pref": "any",
}


def _hammer(targets, rounds=100, threads_each=3):
    """Run every target concurrently and collect any non-200 response."""
    failures = []

    def run(fn):
        for i in range(rounds):
            try:
                res = fn(i)
                if res.status_code != 200:
                    failures.append((fn.__name__, res.status_code, res.get_data(as_text=True)[:200]))
            except Exception as exc:  # pragma: no cover - only on a real break
                failures.append((fn.__name__, "exception", repr(exc)))

    threads = [threading.Thread(target=run, args=(fn,)) for fn in targets for _ in range(threads_each)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return failures


def test_settings_read_write_concurrently(client):
    def read_settings(_i):
        return client.get("/api/settings")

    def write_settings(i):
        return client.post("/api/settings", json={"language": "es" if i % 2 else "en"})

    failures = _hammer([read_settings, write_settings])
    assert failures == [], f"{len(failures)} concurrent request(s) failed: {failures[:3]}"


def test_profile_and_log_writes_concurrently(client):
    """The two writes the user actually hits: finishing onboarding and saving
    a workout, each racing reads of the same data."""
    client.post("/api/profile", json=PROFILE)

    def read_today(_i):
        return client.get("/api/today")

    def write_profile(i):
        return client.post("/api/profile", json={**PROFILE, "weight_kg": 70 + (i % 10)})

    def write_log(i):
        return client.post("/api/log", json={
            "completed": i % 2 == 0, "items_done": [], "items_total": 5,
        })

    failures = _hammer([read_today, write_profile, write_log], rounds=40, threads_each=2)
    assert failures == [], f"{len(failures)} concurrent request(s) failed: {failures[:3]}"
