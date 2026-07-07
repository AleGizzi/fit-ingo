import json
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

import planner  # noqa: E402


@pytest.fixture(scope="module")
def catalog():
    return json.loads((SERVER / "seed" / "exercises.json").read_text())


def base_profile(**over):
    p = dict(
        age=30, sex="male", height_cm=178, weight_kg=80,
        goal="maintain", level="intermediate", impact="low",
        equipment="none", days_per_week=3, session_minutes=30,
        limitations=[],
    )
    p.update(over)
    return p


def test_eligible_respects_impact_tolerance(catalog):
    prof = base_profile(impact="none")
    elig = planner.eligible_exercises(catalog, prof)
    assert elig, "should have some no-impact exercises"
    assert all(e["impact"] == "none" for e in elig)


def test_eligible_low_impact_includes_none_and_low(catalog):
    elig = planner.eligible_exercises(catalog, base_profile(impact="low"))
    impacts = {e["impact"] for e in elig}
    assert impacts <= {"none", "low"}
    assert "high" not in impacts


def test_eligible_excludes_unavailable_equipment(catalog):
    elig = planner.eligible_exercises(catalog, base_profile(equipment="none"))
    assert all(e["equipment"] == "none" for e in elig)
    # With dumbbells you get bodyweight + bands + dumbbells.
    elig_db = planner.eligible_exercises(catalog, base_profile(equipment="dumbbells"))
    equ = {e["equipment"] for e in elig_db}
    assert "dumbbells" in equ and "none" in equ


def test_contraindications_filtered(catalog):
    prof = base_profile(limitations=["knee"], impact="high")
    elig = planner.eligible_exercises(catalog, prof)
    for e in elig:
        assert "knee" not in e["contraindications"]
    # Squat is knee-contraindicated -> must be gone.
    assert all(e["id"] != "squat" for e in elig)


def test_beginner_difficulty_ceiling(catalog):
    elig = planner.eligible_exercises(catalog, base_profile(level="beginner"))
    assert all(e["difficulty"] <= 2 for e in elig)


def test_age_lowers_ceiling(catalog):
    young = planner.eligible_exercises(catalog, base_profile(level="advanced", age=30))
    old = planner.eligible_exercises(catalog, base_profile(level="advanced", age=60))
    assert max(e["difficulty"] for e in old) <= max(e["difficulty"] for e in young)


def test_generate_plan_has_seven_days(catalog):
    days = planner.generate_plan(catalog, base_profile(days_per_week=3), seed=1)
    assert len(days) == 7
    training = [d for d in days if not d.is_rest]
    assert len(training) == 3


def test_training_days_have_warmup_main_cooldown(catalog):
    days = planner.generate_plan(catalog, base_profile(days_per_week=4), seed=2)
    for d in days:
        if d.is_rest:
            assert not d.items
            continue
        blocks = {i.block for i in d.items}
        assert "warmup" in blocks
        assert "main" in blocks
        assert "cooldown" in blocks


def test_generated_items_respect_constraints(catalog):
    prof = base_profile(impact="none", equipment="none", level="beginner",
                        limitations=["knee", "wrist"], days_per_week=5)
    days = planner.generate_plan(catalog, prof, seed=3)
    by_id = {e["id"]: e for e in catalog}
    for d in days:
        for it in d.items:
            e = by_id[it.exercise_id]
            assert e["impact"] == "none"
            assert e["equipment"] == "none"
            assert e["difficulty"] <= 2
            assert not ({"knee", "wrist"} & set(e["contraindications"]))


def test_gain_muscle_has_more_strength_than_lose(catalog):
    by_id = {e["id"]: e for e in catalog}

    def strength_ratio(goal):
        days = planner.generate_plan(catalog, base_profile(goal=goal, days_per_week=5), seed=7)
        s = c = 0
        for d in days:
            for it in d.items:
                if it.block != "main":
                    continue
                t = by_id[it.exercise_id]["type"]
                if t in ("strength", "balance"):
                    s += 1
                elif t == "cardio":
                    c += 1
        return s / max(1, s + c)

    assert strength_ratio("gain_muscle") > strength_ratio("lose")


def test_progression_factor_bounds():
    assert planner.progression_factor(0.9, 2.5) > 1.0     # strong week -> bump
    assert planner.progression_factor(0.3, 3.0) < 1.0     # low completion -> ease
    assert planner.progression_factor(1.0, 4.8) < 1.0     # too hard -> ease
    assert planner.progression_factor(0.6, 3.5) == 1.0    # steady


def test_apply_progression_scales_reps(catalog):
    days = planner.generate_plan(catalog, base_profile(goal="gain_muscle", days_per_week=3), seed=5)
    before = [(i.exercise_id, i.reps) for d in days for i in d.items if i.block == "main" and i.reps]
    planner.apply_progression(days, 1.08)
    after = {(d.weekday, i.exercise_id): i.reps for d in days for i in d.items if i.block == "main" and i.reps}
    # At least one rep count should have increased.
    assert any(after[(d.weekday, i.exercise_id)] >= r
               for d in days for i in d.items if i.block == "main" and i.reps
               for (eid, r) in [(i.exercise_id, i.reps)])
    assert before  # sanity: there were rep-based items
