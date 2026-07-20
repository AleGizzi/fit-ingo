# Changelog

Versions track the PWA (`frontend/src/lib/version.ts`), shown in Settings ▸ Version.

## 1.4.0

- **Guided workout mode** (new default; List view still one tap away) — one
  exercise at a time with real timers: countdowns for timed moves with
  pause/resume, per-set Done for rep moves, skippable rest timers between
  sets, auto-advance, and vibration cues on set/rest/finish. Progress syncs
  with List view and survives reloads.
- **Streak freezes** 🧊 — complete every scheduled day of a week to bank a
  freeze (max 2). A missed day gets bridged automatically: shown as ice,
  never faked as done. Freezes only spend themselves when they can actually
  save the streak.
- **Visible progress** — lifetime reps / minutes / active weeks, a
  "Volume ×" chip showing your plan's progression, and a tappable workout
  history with exercise-level detail.
- **Rest days suggest the feel-good flow** — optional, streak-neutral.
- Haptic feedback on checkmarks, water-goal, and workout completion.
- Groundwork: schema v3 (migrates in place), heart-rate columns for the
  upcoming live-HR feature, normalized history log format.

## 1.3.0

- **Water tracking** — a 💧 card on Today (+250 / +500 ml, undo, progress bar
  toward a configurable daily goal) and optional hourly-style reminders:
  pick the interval and waking window in Settings; nudges stop once the goal
  is reached. Water history resets with profile changes like other activity.
- **Watch & fit-band import** — Progress grows a "Watch & band data" section.
  Import the `.FIT` files a Garmin watch or band records (activities and
  daily wellness) and get: daily-steps chart, resting-heart-rate trend, and
  a recent-activities list (sport, duration, distance, avg/max HR, calories).
  Parsing is fully local (`fitdecode`, pure Python — runs in Termux); no
  Garmin Connect account or cloud involved. Re-importing the same file is
  safe (deduped by activity start time).
- **In-app Garmin setup guide** (Progress → "Garmin setup guide") — 6 steps to
  pair a Garmin over Bluetooth via Gadgetbridge (F-Droid), no Garmin account,
  and feed its .FIT files into the dashboard. Ready for when hardware arrives.
- Schema migrates in place (v1 → v2) — existing data is preserved.

## 1.2.0

- **Bonus mini-sessions** on the Today page — always available, never touch
  the streak: ⚡ **Quick workout** (~10 min full body, respects your profile's
  impact/equipment/limitations), 🪑 **Desk break** (seated/standing moves for
  a pause while working), 🧘 **Feel-good flow** (gentle stretching & mobility).
- Enter on the keyboard advances past the name step in onboarding.

## 1.1.0

- **Fixed intermittent request failures.** Every thread shared one SQLite
  connection, so concurrent requests could reset each other's cursor and a read
  would return a phantom empty row — roughly 2% of requests 500'd at random.
  On device this looked like "Build my plan does nothing" and "the workout
  rating buttons do nothing". Connections are now per-thread.
- Onboarding surfaces the real error instead of silently staying put, and
  offers a retry.
- Language (English / Español) can now be picked on the onboarding welcome
  screen, not just in Settings.
- Settings ▸ Version shows the running version with a **Check for updates**
  button that forces a service-worker check and reloads onto the new build.

## 1.0.0

- Initial release: personalized plans, strict streaks, exercise library with
  videos, progress metrics, diet suggestions, Termux reminders, dark/light
  themes, English/Spanish.
