# P8 — Haptics (runs after P3)

**Model: haiku or sonnet · Tiny · Frontend only**

## Objective

Physical feedback on the moments that matter. Web Vibration API only —
works in Chrome/Android, silently no-ops elsewhere.

## Files touched

- `frontend/src/lib/haptics.ts` (new, ~15 lines)
- Call sites: `Workout.tsx` / `GuidedFlow` (P3), `Today.tsx`,
  `QuickSession.tsx`
- No i18n, no backend, no settings toggle (Android's global vibration
  setting is the opt-out).

## Spec

```ts
// haptics.ts — the only allowed vibrate() call sites go through here.
export const haptic = {
  tick:      () => navigator.vibrate?.(35),          // checkbox on/off
  set:       () => navigator.vibrate?.(100),         // set completed (P3)
  restEnd:   () => navigator.vibrate?.([80, 60, 80]),// rest → work (P3)
  finish:    () => navigator.vibrate?.(200),         // workout complete
  goal:      () => navigator.vibrate?.([60, 40, 60]),// water goal reached
};
```

Wire: exercise check toggle (both Workout list mode and QuickSession),
guided-mode set/rest/finish (P3 leaves the calls in place or you add them),
water goal crossing in `Today.tsx` (`drink()` — fire only on the transition
below→≥goal, not on every tap past it).

## Verify

`npm run build` clean. Playwright can't feel vibration; instead stub it:
`page.addInitScript(() => { (navigator as any).vibrate = (p) => { (window as any).__vibs = ((window as any).__vibs||[]).concat([p]); return true; }; })`
then assert `__vibs` contents after: a checkbox tap, water reaching goal.
Paste the asserted arrays.

## Acceptance

Calls fire exactly per spec (no vibration spam on undo past goal); zero
TypeScript errors; desktop (no `navigator.vibrate`) never throws.
