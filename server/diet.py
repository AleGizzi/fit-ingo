"""Diet suggestions — Mifflin-St Jeor BMR/TDEE, macro split, meal ideas.

Pure functions plus a meal picker that reads ``seed/meals.json``. This is
deliberately simple and rule-based; the API layer attaches the bilingual
"not medical advice" disclaimer from the seed file.
"""

from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent / "seed"

# Activity multiplier chosen from training days/week (Mifflin-St Jeor TDEE).
def activity_factor(days_per_week: int) -> float:
    if days_per_week <= 0:
        return 1.2      # sedentary
    if days_per_week <= 2:
        return 1.375    # light
    if days_per_week <= 4:
        return 1.55     # moderate
    if days_per_week <= 5:
        return 1.725    # active
    return 1.9          # very active


# kcal adjustment applied to TDEE per goal.
GOAL_KCAL_DELTA = {
    "lose": -450,
    "maintain": 0,
    "general": 0,
    "gain_muscle": 300,
}


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor. Returns kcal/day at rest."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if (sex or "").lower().startswith("m"):
        return base + 5
    if (sex or "").lower().startswith("f"):
        return base - 161
    # Unspecified: average the two offsets.
    return base - 78


def targets(profile: dict) -> dict:
    """Compute daily calorie + macro targets for a profile."""
    weight = float(profile.get("weight_kg") or 70)
    height = float(profile.get("height_cm") or 170)
    age = int(profile.get("age") or 30)
    sex = profile.get("sex", "")
    goal = profile.get("goal", "maintain")
    days = int(profile.get("days_per_week") or 3)

    bmr = bmr_mifflin(sex, weight, height, age)
    tdee = bmr * activity_factor(days)
    kcal = tdee + GOAL_KCAL_DELTA.get(goal, 0)
    # Never recommend below a conservative floor.
    floor = 1500 if sex.lower().startswith("m") else 1200
    kcal = max(floor, kcal)

    # Protein-first macros.
    #  - gain_muscle / lose: ~1.8 g/kg protein (muscle retention / growth)
    #  - maintain/general:   ~1.6 g/kg
    protein_per_kg = 1.8 if goal in ("gain_muscle", "lose") else 1.6
    protein_g = round(protein_per_kg * weight)
    # Fat ~25% of calories.
    fat_g = round((kcal * 0.25) / 9)
    # Carbs fill the remainder.
    carb_kcal = kcal - (protein_g * 4) - (fat_g * 9)
    carb_g = round(max(0, carb_kcal) / 4)

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "kcal": round(kcal),
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carb_g": carb_g,
        "water_ml": round(weight * 33),   # ~33 ml/kg rule of thumb
    }


def _load_meals() -> dict:
    return json.loads((SEED_DIR / "meals.json").read_text(encoding="utf-8"))


def suggest_meals(profile: dict, kcal_target: int | None = None) -> dict:
    """Pick one option per slot (breakfast/lunch/dinner + 1 snack) whose total
    lands near the calorie target, respecting a vegetarian preference."""
    data = _load_meals()
    meals = data["meals"]
    veg = profile.get("diet_pref") == "vegetarian"
    goal = profile.get("goal", "maintain")

    if kcal_target is None:
        kcal_target = targets(profile)["kcal"]

    def pool(slot: str) -> list[dict]:
        items = [m for m in meals if m["slot"] == slot]
        if veg:
            items = [m for m in items if "vegetarian" in m["tags"]]
        return items or [m for m in meals if m["slot"] == slot]

    # Preference tags nudge selection by goal.
    prefer = {"lose": "light", "gain_muscle": "high_protein", "maintain": "high_protein"}.get(goal)

    def best(slot: str, budget: int) -> dict:
        items = pool(slot)
        def score(m):
            s = abs(m["kcal"] - budget)
            if prefer and prefer in m["tags"]:
                s -= 60   # small bonus toward the goal-appropriate option
            return s
        return min(items, key=score)

    # Rough budget split across the day.
    split = {"breakfast": 0.28, "lunch": 0.34, "dinner": 0.30, "snack": 0.08}
    chosen = {slot: best(slot, round(kcal_target * frac)) for slot, frac in split.items()}

    total_kcal = sum(m["kcal"] for m in chosen.values())
    total_protein = sum(m["protein_g"] for m in chosen.values())

    return {
        "target_kcal": kcal_target,
        "meals": chosen,
        "total_kcal": total_kcal,
        "total_protein_g": total_protein,
        "note_en": data.get("note_en", ""),
        "note_es": data.get("note_es", ""),
    }
