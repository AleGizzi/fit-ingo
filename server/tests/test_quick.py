import json
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

import quick  # noqa: E402

EXERCISES = json.loads((SERVER / "seed" / "exercises.json").read_text())
# Normalize like db.all_exercises() does: JSON columns become lists.
for e in EXERCISES:
    e.setdefault("contraindications", [])

PROFILE = {
    "goal": "maintain", "level": "beginner", "impact": "low",
    "equipment": "none", "limitations": [], "age": 30,
}


@pytest.mark.parametrize("kind", quick.KINDS)
def test_each_kind_builds(kind):
    s = quick.build_session(EXERCISES, PROFILE, kind, seed=1)
    assert s["kind"] == kind
    assert s["items"], f"{kind} produced an empty session"
    ids = {e["id"] for e in EXERCISES}
    for it in s["items"]:
        assert it["exercise_id"] in ids
        # Shape the workout UI expects (PlanItem).
        for key in ("id", "position", "block", "sets", "reps", "duration_sec", "rest_sec"):
            assert key in it


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        quick.build_session(EXERCISES, PROFILE, "yoga")


def test_quick_is_about_ten_minutes():
    for seed in range(10):
        s = quick.build_session(EXERCISES, PROFILE, "quick", seed=seed)
        assert 6 <= s["minutes"] <= 14, f"seed {seed}: {s['minutes']} min"


def test_desk_pool_only_desk_moves():
    s = quick.build_session(EXERCISES, PROFILE, "desk", seed=2)
    for it in s["items"]:
        assert it["exercise_id"] in quick.DESK_POOL


def test_wellness_pool_only_gentle_moves():
    s = quick.build_session(EXERCISES, PROFILE, "wellness", seed=3)
    for it in s["items"]:
        assert it["exercise_id"] in quick.WELLNESS_POOL


def test_limitations_respected():
    """A wrist limitation must drop chair dips / cat-cow etc. from every kind."""
    limited = {**PROFILE, "limitations": ["wrist", "knee"]}
    contra = {
        e["id"] for e in EXERCISES
        if {"wrist", "knee"} & set(e.get("contraindications") or [])
    }
    assert contra, "seed data lost its contraindications?"
    for kind in quick.KINDS:
        for seed in range(10):
            s = quick.build_session(EXERCISES, limited, kind, seed=seed)
            used = {it["exercise_id"] for it in s["items"]}
            assert not (used & contra), f"{kind} seed {seed} used {used & contra}"
            assert s["items"], f"{kind} seed {seed} became empty under limitations"


def test_no_profile_still_works():
    """Before onboarding (or after reset) the endpoint must not crash."""
    for kind in quick.KINDS:
        s = quick.build_session(EXERCISES, None, kind, seed=4)
        assert s["items"]
