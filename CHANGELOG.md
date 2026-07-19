# Changelog

Versions track the PWA (`frontend/src/lib/version.ts`), shown in Settings ▸ Version.

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
