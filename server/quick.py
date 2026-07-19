"""Bonus mini-sessions, generated on demand and never persisted.

Three kinds, all "besides the weekly goal": they don't touch the plan, the
workout log or the streak — finishing one is its own reward.

- ``quick``     ~10-minute full workout for days you want extra movement.
- ``desk``      ~5 minutes of seated/standing moves for a break while working.
- ``wellness``  ~10 minutes of gentle stretching/mobility to feel better.

Selection reuses the planner's eligibility filter, so impact tolerance,
equipment and limitations from the profile are always respected.
"""

from __future__ import annotations

import random

from planner import GOAL_MIX, PlanItem, eligible_exercises

KINDS = ("quick", "desk", "wellness")

# Everything here is doable at/next to a desk in work clothes: no floor, no
# equipment, nothing that works up a sweat. Order roughly top-down the body.
DESK_POOL = [
    "neck-rolls", "shoulder-rolls", "arm-circles", "wrist-circles",
    "torso-twists", "side-bends", "chest-stretch", "triceps-stretch",
    "chair-squat", "calf-raise", "chair-dip", "ankle-circles", "marching",
]

# A calm head-to-toe flow: mobility to warm the joints, then longer stretches.
WELLNESS_POOL = [
    "neck-rolls", "shoulder-rolls", "hip-circles", "cat-cow", "torso-twists",
    "child-pose", "cobra-stretch", "chest-stretch", "hamstring-stretch",
    "hip-flexor-stretch", "quad-stretch", "figure-four", "butterfly-stretch",
    "calf-stretch",
]


def build_session(exercises: list[dict], profile: dict | None, kind: str,
                  seed: int | None = None) -> dict:
    """Return {kind, minutes, items:[…]} with plan-item-shaped dicts."""
    if kind not in KINDS:
        raise ValueError(f"unknown quick session kind: {kind}")

    profile = profile or {}
    pool = eligible_exercises(exercises, profile)
    by_id = {e["id"]: e for e in pool}
    rng = random.Random(seed)

    if kind == "quick":
        items = _quick_workout(pool, profile, rng)
    elif kind == "desk":
        items = _from_curated(DESK_POOL, by_id, rng, count=6)
    else:
        items = _from_curated(WELLNESS_POOL, by_id, rng, count=8)

    dicts = []
    for pos, it in enumerate(items):
        d = it.to_dict()
        # Match the PlanItem shape the workout UI already renders.
        d["id"] = pos
        d["position"] = pos
        dicts.append(d)
    minutes = _estimate_minutes(items)
    return {"kind": kind, "minutes": minutes, "items": dicts}


def _quick_workout(pool: list[dict], profile: dict, rng: random.Random) -> list[PlanItem]:
    """1 warm-up + 3 main + 1 stretch, everything one set: ~10 minutes."""
    goal = profile.get("goal", "general")
    strength_share = GOAL_MIX.get(goal, GOAL_MIX["general"])["strength"]
    n_strength = max(1, round(3 * strength_share))

    mobility = [e for e in pool if e["type"] == "mobility"]
    strength = [e for e in pool if e["type"] == "strength"]
    cardio = [e for e in pool if e["type"] in ("cardio", "balance")]
    stretch = [e for e in pool if e["type"] == "stretch"]

    exclude: set[str] = set()
    items: list[PlanItem] = []
    for e in _sample(mobility, 1, rng, exclude):
        items.append(PlanItem(e["id"], block="warmup", duration_sec=40, rest_sec=5))

    main = _sample(strength, n_strength, rng, exclude) + \
        _sample(cardio, 3 - n_strength, rng, exclude)
    for e in main:
        if e["type"] in ("cardio", "balance"):
            items.append(PlanItem(e["id"], block="main",
                                  sets=2, duration_sec=40, rest_sec=20))
        else:
            items.append(PlanItem(e["id"], block="main",
                                  sets=2, reps=12, rest_sec=25))

    for e in _sample(stretch, 1, rng, exclude):
        items.append(PlanItem(e["id"], block="cooldown", duration_sec=40, rest_sec=0))
    return items


def _from_curated(pool_ids: list[str], by_id: dict[str, dict],
                  rng: random.Random, count: int) -> list[PlanItem]:
    """Pick from a curated list, keeping its body order but varying the mix.

    Ids missing from by_id were filtered out by the user's limitations
    (or aren't seeded yet) — silently skipped, that's the point.
    """
    available = [i for i in pool_ids if i in by_id]
    chosen = sorted(rng.sample(range(len(available)), min(count, len(available))))
    items = []
    for idx in chosen:
        e = by_id[available[idx]]
        if e["type"] == "strength":
            items.append(PlanItem(e["id"], block="main", sets=1, reps=12, rest_sec=15))
        else:
            items.append(PlanItem(e["id"], block="main", duration_sec=40, rest_sec=10))
    return items


def _sample(pool: list[dict], n: int, rng: random.Random, exclude: set[str]) -> list[dict]:
    candidates = [e for e in pool if e["id"] not in exclude]
    rng.shuffle(candidates)
    chosen = candidates[:max(0, n)]
    exclude.update(e["id"] for e in chosen)
    return chosen


def _estimate_minutes(items: list[PlanItem]) -> int:
    total = 0
    for it in items:
        sets = it.sets or 1
        work = it.duration_sec if it.duration_sec else (it.reps or 10) * 3
        total += sets * (work + (it.rest_sec or 0))
    return max(1, round(total / 60))
