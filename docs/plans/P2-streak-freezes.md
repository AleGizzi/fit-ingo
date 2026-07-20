# P2 — Earned streak freezes (requires P1)

**Model: opus or strong sonnet · Backend-heavy + Today-page UI**

## Objective

Remove the strict streak's rage-quit moment without faking data: users
**earn** freezes by completing full weeks; a freeze silently covers one
missed training day. Max 2 banked. Nothing is auto-completed — a frozen day
is marked frozen, not done.

## Files touched

- `server/streak.py`, `server/app.py` (streak endpoints only)
- `server/tests/test_streak.py` (extend), `server/tests/test_freezes.py` (new)
- `frontend/src/pages/Today.tsx`, `frontend/src/components/WeekRing.tsx`,
  `frontend/src/components/Flame.tsx` (badge only), `today.css`/`weekring.css`
- `frontend/src/lib/types.ts` (Streak type), i18n en/es

## Semantics (frozen — implement exactly)

**Earning.** When the user completes a workout and, after that completion,
*every* training day of the current ISO week that is `<= today` is completed
(or frozen): `freezes = min(2, freezes + 1)`, guarded by
`last_earned_week != current ISO week` (one earn per week). Earning is
evaluated inside `POST /api/log` handling, server-side only.

**Consuming.** Lazily, whenever the streak is computed (`GET /api/streak`,
`/api/today`, `/api/log` response): walk back from yesterday exactly like
`compute_streak` does today; on the **first** missed training day, if
`freezes > 0` and that date is not already in `frozen_dates`: consume one
(persist `freezes-1`, append date to `frozen_dates`) and continue the walk
treating it as covered. A second miss in the same walk consumes a second
freeze if banked, else breaks. **Never** consume for today (today is not
"missed" until it ends — existing rule).

**Compute.** `compute_streak` gains a `frozen_dates: set[str]` parameter:
frozen dates count as continuity (like completed) but are NOT added to any
"completed" count or shown as done.

**API.** `Streak` JSON grows: `{"current", "best", "at_risk",
"freezes": int, "frozen_today": bool, "freeze_just_used": "YYYY-MM-DD"|null}`
— `freeze_just_used` is set only on the response where consumption first
happened (so the UI can toast once), tracked via a `notified` flag or by
comparing pre/post state in the endpoint; keep it simple and stateless if
easier: return the most recent frozen date if it is within the last 7 days
and newer than the previous call is acceptable — **decision**: return
`last_frozen_date` instead, UI decides freshness. Update `types.ts`
accordingly.

**Wipes.** Profile change / reset already clears streak_state (P1).

## UI

- Streak card (Today): under `streakBest`, a freeze row: `🧊 ×N` with
  tooltip-ish label `t("streak.freezes")`. When `current > 0` and a recent
  frozen date exists in this week, show a subtle banner:
  "🧊 A freeze saved your streak on {date}".
- WeekRing: frozen days render as a distinct state `"frozen"` (ice-blue
  `#38bdf8` ring, not mint) — extend `DayState` union + `buildWeekStates`
  (frontend gets frozen dates from the streak payload; pass this week's).
- i18n keys: `streak.freezes` ("Streak freezes"), `streak.frozenBanner`
  ("A freeze saved your streak on {{date}}"), `streak.earned`
  ("Full week! +1 streak freeze 🧊") — the earned toast shows on the workout
  celebration screen when the log response's `freezes` increased (`Workout.tsx`
  already receives the streak in `finish()`; compare with pre-save value from
  `/api/today` payload… simplest: response includes `freeze_earned: bool`).

Add `freeze_earned: bool` to the `POST /api/log` response contract.

## Edge cases that MUST have tests

1. Miss one training day with 1 banked → streak continues, freezes 0,
   date recorded, second read does not double-consume.
2. Miss two consecutive training days with 1 banked → breaks (current
   resets), the single freeze covers only the first miss.
3. Earn: completing the last scheduled day of the week grants +1 exactly
   once (repeat POST /api/log same day → no second grant).
4. Cap at 2.
5. Rest days never consume or earn.
6. Freeze never consumed for *today* while today is incomplete.
7. `best` accounting unchanged apart from freeze continuity.
8. Profile change → freezes and frozen_dates gone (already-P1 test; assert
   via API here).

## Verify

```bash
cd server && ../.venv/bin/python -m pytest -q
cd frontend && npm run build   # + parity check from README
```

Then boot a QA server (`FITINGO_DB=<scratch>/qa.db FITINGO_PORT=8794`),
backdate logs via `POST /api/log {"date": ...}` to construct scenario (1),
and confirm `GET /api/streak` shows continuity + `freezes: 0`. Paste the
curl outputs in your report.

## Acceptance

All 8 scenario tests green; UI states verified in a `tools/uicheck`
screenshot (frozen day visible in WeekRing, freeze count on streak card);
no change to plain-strict behavior when `freezes == 0` (existing streak
tests must pass unmodified except for the new parameter's default).
