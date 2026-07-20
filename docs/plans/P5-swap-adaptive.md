# P5 — Exercise swap + adaptive difficulty (requires P1)

**Model: opus or strong sonnet · Planner reasoning**

## Objective

Two feedback loops: (1) swap any exercise for an eligible alternative,
optionally excluding it from future plans; (2) let perceived-difficulty
ratings nudge the next plan generation.

## Files touched

- `server/app.py` (2 endpoints), `server/planner.py` (adaptive hook),
  `server/db.py` **read-only use** of P1's `excluded_exercises` helpers
- `server/tests/test_swap_adaptive.py` (new)
- `frontend/src/pages/Workout.tsx` (swap affordance in List mode; in Guided
  mode a small "swap" icon on the card header — coordinate: P3 lands first),
  `frontend/src/lib/{api,types}.ts`, i18n en/es

## Backend

### `POST /api/plan/swap`
Body: `{"plan_item_id": int, "exclude": bool}`.
Behavior:
1. Load the plan item + its exercise. Build the eligible pool via
   `planner.eligible_exercises(db.all_exercises(), profile)` minus
   `db.get_excluded_exercises()` minus exercises already in that plan day.
2. Prefer same `type` AND ≥1 shared `muscle_groups` entry; fallback same
   `type`; fallback any eligible. If pool empty → 409 `{"error": ...}`
   (UI shows a toast, keeps the original).
3. Replace the plan item's `exercise_id` in place (same sets/reps/duration —
   they were sized for the slot, keep them), return the updated item JSON.
4. If `exclude`: append the old exercise id to `excluded_exercises`
   (via P1 helper, dedup).

### Adaptive difficulty (planner)
In `generate_plan` / the regenerate path, before selection:
- Pull the last 6 `workout_log` rows with `perceived_difficulty` not null.
- `avg >= 4.3` → effective difficulty ceiling `-1` (floor 1);
  `avg <= 1.7` and completion of those logs ≥ 80% → ceiling `+1`
  (never above `LEVEL_MAX_DIFFICULTY[level]` — the level cap stays a cap).
- Always subtract `excluded_exercises` from the pool (in
  `eligible_exercises` via a new optional param `excluded: set[str]`, or
  filtered at call sites — pick one, apply consistently including
  `quick.py`'s `build_session`, which must also respect exclusions).
- Log the applied adjustment into plan `meta`
  (`"adaptive": {"avg_perceived": 4.5, "ceiling_delta": -1}`) so P4's UI
  could surface it later.

### Settings escape hatch
`excluded_exercises` should be listable/clearable: extend the existing
`PATCH`-like surface — simplest: `POST /api/settings` already round-trips
settings; expose `excluded_exercises` there (P1 already stores it in
settings). Frontend: in the **Library** page, excluded exercises get a
muted "excluded" badge and a tap-to-restore.

## Frontend

- Workout List mode: long-press (or a small `⇄` button — buttons are more
  discoverable on mobile; use the button) on a not-done exercise card →
  action sheet: "Swap for something similar" / "Swap and don't suggest
  again" / cancel. On success, replace the card in place (returned item),
  reset its done state.
- Guided mode: `⇄` in the card header does the same for the current item.
- Library: "excluded" badge + restore (see above).
- i18n: `workout.swap`, `workout.swapExclude`, `workout.swapNone`
  ("No alternative available"), `library.excluded`, `library.restore`.

## Tests (must exist)

1. Swap returns same-type, muscle-overlapping alternative when available;
   respects impact/equipment/limitations (fixture: knee limitation → no
   contraindicated replacement).
2. `exclude: true` persists; the next `POST /api/plan/regenerate` never
   selects that id; `GET /api/quick/*` never returns it either.
3. Empty pool → 409, plan unchanged.
4. Adaptive: seed 6 logs rated 5 → regen plan's items all have
   difficulty ≤ old ceiling −1. Seed ratings 1 + high completion → +1,
   capped by level. No ratings → unchanged.
5. Ceiling floor at 1 (beginner rating everything 5 doesn't zero the pool).

## Verify

Standard: pytest green, build clean, parity OK. Playwright: swap a card in
List mode, screenshot before/after; exclude one, regenerate from Settings,
confirm via `GET /api/plan` (curl) it's gone. Paste outputs.

## Acceptance

All 5 tests green; swap UX works in both modes; excluded list visible and
reversible in Library; `quick.py` respects exclusions.
