# P10 — Exercise illustrations (79 SVGs, offline-first)

**Model: sonnet (loopable in batches) · Art-spec discipline over creativity**

## Objective

Every exercise gets a small line-art illustration so the app teaches form
without YouTube or a connection. Uniformity beats beauty: 79 mediocre-but-
consistent figures look professional; 79 individually-clever ones look like
a sticker album.

## Files touched

- `frontend/src/assets/exercises/<id>.svg` × 79 (ids from
  `server/seed/exercises.json`)
- `frontend/src/components/ExerciseArt.tsx` (new loader + fallback)
- Mount points: `Workout.tsx` cards, P3 guided card, `Library.tsx`,
  `QuickSession.tsx`
- `tools/artcheck.mjs` (new, spec linter — see below)

## Art spec (hard rules — the linter enforces what it can)

1. `viewBox="0 0 96 96"`, no width/height attributes.
2. Stick figure style: `stroke="currentColor"`, `stroke-width="3"`,
   `stroke-linecap="round"`, `stroke-linejoin="round"`, `fill="none"` on
   every path. **No other colors, no fills, no gradients, no text.** One
   accent allowed: a single element may use `stroke="var(--ember)"` to
   highlight the working body part or movement arrow.
3. Head = circle r≈7. Body proportions consistent across all files
   (torso ~22, limbs ~18–20 units).
4. Depict the exercise's *key frame* (bottom of a squat, top of a push-up),
   plus at most one motion arrow.
5. Props allowed where the exercise needs them: chair (4 lines), wall
   (1 line), dumbbell (line + 2 small circles), band (1 dashed line).
6. ≤ 2 KB per file, no `<style>`, no scripts, no external refs.

## Loader

```tsx
// ExerciseArt.tsx — eager glob so Vite inlines/bundles at build time.
const arts = import.meta.glob("../assets/exercises/*.svg", {
  eager: true, query: "?raw", import: "default" });
export function ExerciseArt({ id, type }: { id: string; type?: string }) {
  const raw = arts[`../assets/exercises/${id}.svg`] as string | undefined;
  if (!raw) return <span className="ex-art-fallback">{TYPE_EMOJI[type ?? ""] ?? "🏋️"}</span>;
  return <span className="ex-art" dangerouslySetInnerHTML={{ __html: raw }} />;
}
```
`.ex-art svg { width: 56px; height: 56px; color: var(--ink-2); }` — inherits
theme via currentColor, so dark mode is free. (Raw-inline is safe here: the
SVGs are first-party, linter-checked assets, not user input.)

## Spec linter (`tools/artcheck.mjs`)

Node script, no deps: for each seed exercise id assert a file exists; for
each file assert viewBox, no fill≠none, no stroke colors besides
currentColor/var(--ember), size ≤ 2048 bytes, no `<script`/`<style`/`href`.
Exit non-zero with a per-file report. Run it in Verify.

## Batching strategy (for the orchestrator)

Loop batches of ~10 by muscle group (squat family, push family, core,
cardio, stretches, band/dumbbell) so poses stay comparable within a batch.
After each batch: run artcheck + a Library screenshot; the orchestrator eyeballs
consistency before the next batch. Rework beats accumulation.

## Verify

```bash
node tools/artcheck.mjs                     # 79/79 pass
cd frontend && npm run build                # bundle delta noted in report
```
Playwright: Library page screenshot (grid of arts, both themes), one Workout
card, one guided card. The orchestrator judges visual consistency — expect
to redo outliers.

## Acceptance

79/79 ids covered and linter-clean; bundle growth < 160 KB total; fallback
emoji renders for an unknown id (unit/browser check); Library looks uniform
in light *and* dark screenshots.
