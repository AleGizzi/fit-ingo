# P9 — Live heart rate via Web Bluetooth (requires P1; hardware verify deferred)

**Model: sonnet · Frontend-heavy + tiny backend passthrough**

## Objective

Connect any standard BLE heart-rate device (chest strap, or a watch in
"Broadcast HR" mode) directly to the PWA — no apps in between — show live
bpm during workouts, save avg/max into the workout log.

Works because the app runs on `http://localhost`, which is a secure context,
and Chrome/Android implements Web Bluetooth. **No hardware exists to test
against yet** — build behind feature detection, verify with a mock, leave a
hardware checklist for the owner.

## Files touched

- `frontend/src/lib/ble-hr.ts` (new: connection + parser)
- `frontend/src/pages/Workout.tsx` + P3's guided card (`{/* P9 */}` marker)
- `frontend/src/lib/{api,types}.ts` (log payload + Workout log fields)
- `server/app.py::log_workout` (accept `avg_hr`/`max_hr` → P1's columns)
- `server/tests/test_log_hr.py` (new, trivial)
- i18n en/es

## BLE spec (implement exactly — this is standards work, not invention)

- `navigator.bluetooth.requestDevice({ filters: [{ services: ["heart_rate"] }] })`
  — must be called from a user gesture (the connect button's onClick).
- GATT: primary service `heart_rate` (0x180D) → characteristic
  `heart_rate_measurement` (0x2A37) → `startNotifications()`.
- Parser (pure function, unit-tested):
  byte0 flags — bit0: 0 ⇒ HR is uint8 at byte1; 1 ⇒ uint16 LE at bytes1–2.
  Ignore energy/RR fields. `parseHrm(dv: DataView): number`.
- Handle `gattserverdisconnected` → status "disconnected", allow reconnect.
  Disconnect cleanly on page unmount/finish.

## UX

- In the workout top bar (both modes): if `"bluetooth" in navigator`, show a
  small `♥` chip button. States: idle (`♥ Connect`), connecting, live
  (`♥ 132` pulsing ember), disconnected (tap to reconnect). If the API is
  absent → render nothing (Firefox/desktop Safari).
- Session stats collected in a ref: every notification appends bpm;
  `avg = round(mean)`, `max`. On `finish()`, include `avg_hr`/`max_hr` in
  `api.logWorkout` when ≥ 30 samples exist (below that it's noise — omit).
- P4's history rows already display `avg_hr`/`max_hr` when present (they're
  in the endpoint contract) — verify they show once data exists.
- i18n: `hr.connect`, `hr.connecting`, `hr.disconnected`, `hr.live` (label
  only; number is numeric).

## Backend

`log_workout()`: accept optional ints `avg_hr`, `max_hr`, store into P1's
columns (validate 30–250 else ignore). Include in `/api/history` output
(P4 contract already has the fields).

## Testing without hardware

1. Unit-test `parseHrm` against crafted DataViews: uint8 case (0x00, 78),
   uint16 case (0x01, 0x40, 0x01 → 320 — accept, range-clamp happens
   server-side), flags with extra bits set.
2. Playwright: inject a fake `navigator.bluetooth` whose device/GATT emits
   20 synthetic notifications (60→150 bpm ramp) via `page.addInitScript`;
   assert the chip shows live values and the POST body contains plausible
   avg/max (intercept the request).
3. Feature-absence: delete `navigator.bluetooth` in an init script → chip
   absent, zero console errors.

## Hardware checklist (leave in the report for the owner)

- [ ] Pixel + Polar/Garmin broadcast: chip appears, pairs, live bpm sane
- [ ] Walk out of range → "disconnected" state, reconnect works
- [ ] Finished workout shows avg/max in Progress history

## Acceptance

Parser unit tests green; both Playwright scenarios pass; log round-trip test
green; absolutely no behavior change when Bluetooth is unavailable.
