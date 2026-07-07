import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

import diet  # noqa: E402


def test_bmr_male_known_value():
    # Mifflin-St Jeor: 10*80 + 6.25*180 - 5*30 + 5 = 1780
    assert round(diet.bmr_mifflin("male", 80, 180, 30)) == 1780


def test_bmr_female_known_value():
    # 10*60 + 6.25*165 - 5*30 - 161 = 1320.25
    assert round(diet.bmr_mifflin("female", 60, 165, 30)) == 1320


def test_activity_factor_increases_with_days():
    assert diet.activity_factor(0) < diet.activity_factor(3) < diet.activity_factor(6)


def test_lose_goal_below_maintain():
    base = dict(sex="male", weight_kg=80, height_cm=180, age=30, days_per_week=3)
    lose = diet.targets({**base, "goal": "lose"})
    maintain = diet.targets({**base, "goal": "maintain"})
    gain = diet.targets({**base, "goal": "gain_muscle"})
    assert lose["kcal"] < maintain["kcal"] < gain["kcal"]


def test_calorie_floor_enforced():
    # Tiny person on a cut should still not drop below the floor.
    t = diet.targets(dict(sex="female", weight_kg=45, height_cm=150, age=25,
                          days_per_week=0, goal="lose"))
    assert t["kcal"] >= 1200


def test_macros_sum_close_to_calories():
    t = diet.targets(dict(sex="male", weight_kg=80, height_cm=180, age=30,
                          days_per_week=4, goal="maintain"))
    macro_kcal = t["protein_g"] * 4 + t["carb_g"] * 4 + t["fat_g"] * 9
    assert abs(macro_kcal - t["kcal"]) <= 30


def test_protein_higher_for_muscle_goal():
    base = dict(sex="male", weight_kg=80, height_cm=180, age=30, days_per_week=4)
    gain = diet.targets({**base, "goal": "gain_muscle"})
    maintain = diet.targets({**base, "goal": "maintain"})
    assert gain["protein_g"] > maintain["protein_g"]


def test_suggest_meals_vegetarian_only():
    prof = dict(sex="female", weight_kg=65, height_cm=168, age=28,
                days_per_week=3, goal="maintain", diet_pref="vegetarian")
    s = diet.suggest_meals(prof)
    for slot, meal in s["meals"].items():
        assert "vegetarian" in meal["tags"], f"{slot} not vegetarian"


def test_suggest_meals_covers_all_slots():
    prof = dict(sex="male", weight_kg=80, height_cm=180, age=30,
                days_per_week=4, goal="lose")
    s = diet.suggest_meals(prof)
    assert set(s["meals"].keys()) == {"breakfast", "lunch", "dinner", "snack"}
    assert s["total_kcal"] > 0 and s["total_protein_g"] > 0
