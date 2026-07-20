# P3 — Guided workout mode (timers, auto-advance)

**Model: sonnet · Frontend only · The biggest UX packet**

## Objective

Turn the workout from a checklist into a coached flow: one exercise at a
time, work/rest timers that actually count, auto-advance, vibration cues.
The checklist stays available as a secondary view; the guided flow becomes
the default entry from "Start workout".

## Files touched

- `frontend/src/pages/Workout.tsx` (mode switch + shared state)
- `frontend/src/pages/GuidedFlow.tsx` (new component, may live in pages/)
- `frontend/src/pages/workout.css` (extend)
- `frontend/src/lib/types.ts` if needed; i18n en/es
- **No backend changes.** `POST /api/log` is used exactly as today.

## Current state

`Workout.tsx` renders grouped cards (`warmup|main|cooldown`), checkmarks in
`doneIds` keyed by `itemKey(it) = "${exercise_id}:${block}:${position}"`,
autosaves partial progress (completed=false, 600 ms debounce), `finish()`
POSTs and handles errors. Review mode when `today.log.completed`.

## Spec

### Mode switch
- Top bar gets a segmented toggle: `Guided | List` (i18n `workout.guided`,
  `workout.list`). Default Guided for a fresh session; if the session was
  resumed with >0 items done, keep Guided but start at the first not-done
  item. Review mode always uses List (unchanged).

### Guided flow, per plan item
- Card shows: block eyebrow, exercise name, dose (`itemDose`), instructions,
  video link — same data as list cards, one at a time, centered, big.
- **Rep-based items** (`reps != null`): no countdown. Big `Done ✓` button
  per set: "Set 1 of 3 — 12 reps" → tap → rest timer → next set.
- **Duration-based items** (`duration_sec != null`): circular/linear
  countdown of `duration_sec`, Start/Pause, auto-completes the set at 0.
- **Rest**: after each set except the item's last, countdown `rest_sec`
  (skippable via "Skip rest"). After the item's last set, mark the item done
  in `doneIds` (same key function — autosave keeps working for free) and
  advance to the next item.
- Progress bar on top = same `doneCount/total` as list mode. Both modes
  share `doneIds` state — switching modes mid-session must not lose ticks.
- Last item done → open the existing rating sheet (reuse as-is).
- Back (`✕`) keeps current behavior (autosave already covers state).

### Timers — correctness requirements
- Drive from wall-clock deltas (`Date.now()` captured at start), not
  `setInterval` accumulation, so a backgrounded tab stays correct.
- On `visibilitychange` back to visible, recompute remaining from the
  stored end-timestamp.
- Cleanup on unmount (no interval leaks — StrictMode double-mount safe).

### Cues
- `navigator.vibrate?.(...)`: 100 ms at set completion, [80,60,80] when rest
  ends, 200 ms when the whole workout completes. Always feature-detected
  (desktop Chrome returns undefined — never crash).
- Rest→work transition also flashes the timer color (mint→ember).

### i18n (en + es)
`workout.guided`, `workout.list`, `workout.setOf` ("Set {{n}} of {{total}}"),
`workout.rest` ("Rest"), `workout.skipRest` ("Skip rest"),
`workout.getReady` ("Get ready"), `workout.pause`, `workout.resumeTimer`.

## Out of scope

Backend, sounds/TTS, reordering exercises, HR display (P9 slots into the
guided card later — leave a clearly-marked `{/* P9: hr chip mounts here */}`
comment in the guided card header).

## Verify

```bash
cd frontend && npm run build     # strict TS clean
# parity check from README
```

Playwright (`tools/uicheck`, server on 127.0.0.1:8794 with a seeded profile):
1. Start workout → guided card 1 visible, `Set 1 of N` label correct.
2. Duration item: assert countdown text decreases across a 2 s wait.
3. Complete all sets of item 1 → rest runs → item 2 appears; progress `1/N`.
4. Switch to List mid-flow → tick states match; switch back → guided resumes
   at first not-done item.
5. Finish last item → rating sheet appears; rate → celebration → /today.
6. Reload mid-flow → resumed with autosaved ticks.
Screenshot each step. Paste console output + attach shots in the report.

## Acceptance

All 6 flows pass; timers survive tab-hide (test via
`page.evaluate(() => document.dispatchEvent(...))` or by CDP page freeze if
practical — at minimum unit-test the remaining-time math as a pure function);
list mode and review mode behave exactly as before.
