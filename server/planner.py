"""Workout program generator — a pure rules engine (no ML, no network).

Given a profile and the exercise catalog, ``generate_plan`` returns a weekly
program: which weekdays are training days, and for each an ordered list of
warm-up / main / cool-down items with sets/reps or durations.

Everything here is a pure function of its inputs so it can be unit-tested
without a database. ``app.py`` handles persistence.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# Goal -> how the main block is split across movement types.
# Weights are relative; they bias how many slots each type gets.
GOAL_MIX = {
    "lose":        {"strength": 0.45, "cardio": 0.55},   # more conditioning
    "maintain":    {"strength": 0.55, "cardio": 0.45},
    "gain_muscle": {"strength": 0.80, "cardio": 0.20},   # strength volume
    "general":     {"strength": 0.55, "cardio": 0.45},
}

IMPACT_RANK = {"none": 0, "low": 1, "high": 2}

# Difficulty ceiling by level. Age >= 55 pulls the ceiling down by one.
LEVEL_MAX_DIFFICULTY = {"beginner": 2, "intermediate": 3, "advanced": 5}

# How many distinct training days for a given days_per_week request.
# We also cap by a sensible max so nobody trains 7 days.
MAX_TRAINING_DAYS = 6

# Preferred weekday spreads so rest days are distributed, not clustered.
# weekday: 0=Mon .. 6=Sun
DAY_SPREAD = {
    1: [2],
    2: [1, 4],
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 3, 4],
    6: [0, 1, 2, 3, 4, 5],
}


@dataclass
class PlanItem:
    exercise_id: str
    block: str            # warmup | main | cooldown
    sets: int | None = None
    reps: int | None = None
    duration_sec: int | None = None
    rest_sec: int = 30

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise_id,
            "block": self.block,
            "sets": self.sets,
            "reps": self.reps,
            "duration_sec": self.duration_sec,
            "rest_sec": self.rest_sec,
        }


@dataclass
class PlanDay:
    weekday: int
    is_rest: bool = False
    focus: str = ""
    items: list[PlanItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "weekday": self.weekday,
            "is_rest": self.is_rest,
            "focus": self.focus,
            "items": [i.to_dict() for i in self.items],
        }


def _difficulty_ceiling(profile: dict) -> int:
    ceiling = LEVEL_MAX_DIFFICULTY.get(profile.get("level", "beginner"), 2)
    if (profile.get("age") or 0) >= 55:
        ceiling = max(1, ceiling - 1)
    return ceiling


def eligible_exercises(exercises: list[dict], profile: dict) -> list[dict]:
    """Filter the catalog by the user's constraints.

    - impact must be <= the user's tolerance
    - equipment must be available (bodyweight always allowed)
    - difficulty <= ceiling from level/age
    - drop anything contraindicated by the user's limitations
    """
    tol = IMPACT_RANK.get(profile.get("impact", "low"), 1)
    owned = _owned_equipment(profile.get("equipment", "none"))
    ceiling = _difficulty_ceiling(profile)
    limits = set(profile.get("limitations") or [])

    out = []
    for e in exercises:
        if IMPACT_RANK.get(e["impact"], 2) > tol:
            continue
        if e["equipment"] not in owned:
            continue
        if e["difficulty"] > ceiling:
            continue
        if limits & set(e.get("contraindications") or []):
            continue
        out.append(e)
    return out


def _owned_equipment(equipment: str) -> set[str]:
    """Map the profile's equipment choice to the set of usable tags.
    Bodyweight ("none") is always available; owning dumbbells implies bands
    are fine too (both are 'has some resistance tool')."""
    owned = {"none"}
    if equipment == "bands":
        owned |= {"bands"}
    elif equipment == "dumbbells":
        owned |= {"bands", "dumbbells"}
    return owned


def _pick(pool: list[dict], n: int, rng: random.Random, exclude: set[str]) -> list[dict]:
    candidates = [e for e in pool if e["id"] not in exclude]
    rng.shuffle(candidates)
    chosen = candidates[:n]
    exclude.update(e["id"] for e in chosen)
    return chosen


def _main_block_size(session_minutes: int) -> int:
    """Roughly how many main exercises fit in a session.
    ~5 min of warm-up + ~4 min cool-down, ~4 min per main exercise incl. rest."""
    usable = max(10, session_minutes - 9)
    return max(3, min(8, round(usable / 4)))


def _reps_for(exercise: dict, profile: dict) -> PlanItem:
    """Assign sets/reps or a duration appropriate to the exercise type and goal."""
    goal = profile.get("goal", "general")
    etype = exercise["type"]

    if etype in ("mobility", "stretch"):
        return PlanItem(exercise["id"], block="warmup",
                        duration_sec=30, rest_sec=10)

    if etype == "cardio":
        dur = {"lose": 45, "maintain": 40, "gain_muscle": 30, "general": 40}.get(goal, 40)
        sets = 3 if profile.get("level") != "beginner" else 2
        return PlanItem(exercise["id"], block="main",
                        sets=sets, duration_sec=dur, rest_sec=20)

    if etype == "balance":
        return PlanItem(exercise["id"], block="main",
                        sets=2, duration_sec=30, rest_sec=15)

    # strength
    if goal == "gain_muscle":
        sets, reps, rest = 4, 8, 60
    elif goal == "lose":
        sets, reps, rest = 3, 15, 30
    else:
        sets, reps, rest = 3, 12, 45
    if profile.get("level") == "beginner":
        sets = max(2, sets - 1)
    # Isometric holds (plank, wall sit) are duration-based.
    if exercise["id"] in ("plank", "side-plank", "wall-sit", "single-leg-stand"):
        return PlanItem(exercise["id"], block="main",
                        sets=sets, duration_sec=30, rest_sec=rest)
    return PlanItem(exercise["id"], block="main",
                    sets=sets, reps=reps, rest_sec=rest)


def _training_weekdays(days_per_week: int) -> list[int]:
    d = max(1, min(MAX_TRAINING_DAYS, days_per_week))
    return DAY_SPREAD[d]


def generate_plan(exercises: list[dict], profile: dict, seed: int | None = None) -> list[PlanDay]:
    """Build a full week (7 PlanDay objects, Mon..Sun)."""
    rng = random.Random(seed)
    pool = eligible_exercises(exercises, profile)

    by_type: dict[str, list[dict]] = {}
    for e in pool:
        by_type.setdefault(e["type"], []).append(e)

    warmups = by_type.get("mobility", [])
    cooldowns = by_type.get("stretch", [])
    strength = by_type.get("strength", []) + by_type.get("balance", [])
    cardio = by_type.get("cardio", [])

    goal = profile.get("goal", "general")
    mix = GOAL_MIX.get(goal, GOAL_MIX["general"])
    train_days = set(_training_weekdays(profile.get("days_per_week", 3)))
    n_main = _main_block_size(profile.get("session_minutes", 30))

    days: list[PlanDay] = []
    for wd in range(7):
        if wd not in train_days:
            days.append(PlanDay(weekday=wd, is_rest=True, focus="rest"))
            continue

        used: set[str] = set()
        items: list[PlanItem] = []

        # Warm-up: 2 mobility drills (fall back to stretches if catalog thin).
        for e in _pick(warmups or cooldowns, 2, rng, used):
            items.append(_reps_for(e, profile))

        # Main block: split slots between strength and cardio per goal mix.
        n_cardio = round(n_main * mix["cardio"]) if cardio else 0
        n_strength = n_main - n_cardio
        main_items: list[PlanItem] = []
        for e in _pick(strength, n_strength, rng, used):
            main_items.append(_reps_for(e, profile))
        for e in _pick(cardio, n_cardio, rng, used):
            main_items.append(_reps_for(e, profile))
        # If one pool was too small, backfill from whatever's left.
        deficit = n_main - len(main_items)
        if deficit > 0:
            for e in _pick(strength + cardio, deficit, rng, used):
                main_items.append(_reps_for(e, profile))
        rng.shuffle(main_items)
        items.extend(main_items)

        # Cool-down: 2 stretches.
        for e in _pick(cooldowns or warmups, 2, rng, used):
            it = _reps_for(e, profile)
            it.block = "cooldown"
            items.append(it)

        focus = _focus_label(main_items, exercises)
        days.append(PlanDay(weekday=wd, is_rest=False, focus=focus, items=items))

    return days


def _focus_label(main_items: list[PlanItem], exercises: list[dict]) -> str:
    """Pick a short focus label from the muscle groups worked most that day."""
    by_id = {e["id"]: e for e in exercises}
    counts: dict[str, int] = {}
    for it in main_items:
        e = by_id.get(it.exercise_id)
        if not e:
            continue
        for g in e["muscle_groups"]:
            counts[g] = counts.get(g, 0) + 1
    if not counts:
        return "full_body"
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
    return "+".join(g for g, _ in top)


# ---- weekly progression --------------------------------------------------

def progression_factor(completion_ratio: float, avg_difficulty: float) -> float:
    """Return a multiplier for reps/duration for the next week.

    - strong week (>=80% done, felt easy) -> bump ~8%
    - struggling week (<50% done, or felt very hard) -> ease off ~10%
    - otherwise hold steady
    """
    if completion_ratio >= 0.8 and avg_difficulty <= 3.0:
        return 1.08
    if completion_ratio < 0.5 or avg_difficulty >= 4.5:
        return 0.90
    return 1.0


def apply_progression(days: list[PlanDay], factor: float) -> list[PlanDay]:
    """Scale reps/durations of main-block items by ``factor`` (rounded sanely)."""
    if factor == 1.0:
        return days
    for day in days:
        for it in day.items:
            if it.block != "main":
                continue
            if it.reps is not None:
                it.reps = max(5, round(it.reps * factor))
            if it.duration_sec is not None:
                it.duration_sec = max(15, round(it.duration_sec * factor / 5) * 5)
    return days
