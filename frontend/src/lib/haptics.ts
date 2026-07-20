// P8 — the only allowed vibrate() call sites go through here.
// navigator.vibrate exists on Chrome/Android; everywhere else these no-op.
export const haptic = {
  /** checkbox on/off */
  tick: () => navigator.vibrate?.(35),
  /** a set completed (guided mode) */
  set: () => navigator.vibrate?.(100),
  /** rest over, back to work */
  restEnd: () => navigator.vibrate?.([80, 60, 80]),
  /** whole workout complete */
  finish: () => navigator.vibrate?.(200),
  /** water goal reached */
  goal: () => navigator.vibrate?.([60, 40, 60]),
};
