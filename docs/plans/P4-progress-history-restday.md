# P4 — Progression visibility, workout history, rest-day content

**Model: sonnet · One small endpoint + Progress/Today UI**

## Objective

Make earned progress *visible*: lifetime totals, weekly volume trend, a
tappable history of past workouts, and rest days that suggest the existing
wellness flow instead of dead-ending.

## Files touched

- `server/app.py` (extend `/api/metrics` or add `GET /api/history`)
- `server/tests/test_history.py` (new)
- `frontend/src/pages/Progress.tsx` + `progress.css`
- `frontend/src/pages/Today.tsx` (rest-day card button only)
- `frontend/src/lib/{api,types}.ts`, i18n en/es

## Backend

### `GET /api/history?limit=30`
Returns completed/attempted days, newest first:

```json
[{"date": "2026-07-18", "completed": 1, "items": [
   {"exercise_id": "squat", "block": "main", "position": 2, "done": true}],
  "items_total": 8, "perceived_difficulty": 4, "avg_hr": null, "max_hr": null}]
```

Reconstruct `items` by joining the day's `items_done` keys
(`id:block:position` — P1 normalized; tolerate legacy bare ids by treating
them as done-markers without position) against the *active plan's* items for
that weekday. If the plan changed since, unmatched keys still render from the
key's exercise_id (name lookup happens client-side) — never 500 on stale keys.

### Lifetime totals — extend `/api/metrics.totals`
Add: `total_reps` (sum of sets×reps over completed items, rep-based only),
`total_minutes` (sum duration_min where present, else estimate 4 min/item),
`weeks_active` (distinct ISO weeks with ≥1 completed log). Compute in SQL +
Python; no schema change.

### Progression factor surface
`GET /api/plan` already returns `meta` — ensure regenerate stores
`progression_factor` into plan meta (check `_regenerate_for_profile` /
`regenerate` route in app.py; add if missing). Frontend reads it from there.

## Frontend

### Progress page
- New stat row under the existing grid: `total_reps` ("reps all-time"),
  `total_minutes` ("minutes trained"), `weeks_active`.
- "This plan: volume ×{factor}" chip near the title when
  `plan.meta.progression_factor` exists and ≠ 1 (one decimal, e.g. ×1.15,
  mint when >1).
- **History list** (new card, above the Health section): last 14 entries,
  each row = date, ✓/✗, `n/total`, difficulty emoji (reuse the 5-emoji scale
  from the rating sheet). Tapping expands inline (no route) to the item list
  with done/missed ticks. Empty state: existing `progress.noData` string.

### Today rest-day card
Add a button under `restBody`:
`🧘 t("quick.wellnessTitle")` → `nav("/quick/wellness")`, plus caption
`t("today.restBonus")` = "Optional — it won't touch your streak." / ES
equivalent. **Do not** change streak semantics; it's a plain link to the
existing quick session.

### i18n
`progress.totalReps`, `progress.totalMinutes`, `progress.weeksActive`,
`progress.volumeChip` ("Volume ×{{f}}"), `progress.history`,
`today.restBonus`. Both languages.

## Out of scope

Editing/deleting history, charts for history, per-exercise PB detection
(future), any streak change.

## Verify

```bash
cd server && ../.venv/bin/python -m pytest -q
cd frontend && npm run build   # + parity check
```

Tests: history endpoint with (a) modern keys, (b) legacy bare-id keys,
(c) a key referencing an exercise no longer in the plan — all render,
none 500. Totals math on a seeded 3-workout fixture.

Playwright: seed 3 backdated logs via `POST /api/log {"date":...}`, open
Progress → history rows visible, tap to expand, screenshot; rest-day Today →
wellness button navigates. Paste outputs.

## Acceptance

History renders all three key formats; totals match hand-computed fixture
values; rest-day button works; existing Progress features (weight chart,
consistency, health section) untouched and visible in the screenshot.
