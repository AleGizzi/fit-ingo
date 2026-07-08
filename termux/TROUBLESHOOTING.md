# Fit-ingo — Troubleshooting

## Notifications aren't showing up

Android notifications from Fit-ingo require **two separate things, and both are required**:

1. **The Termux:API app** — a separate Android app installed from the **same source** as Termux (both from **F-Droid**, or both from Google Play). Never mix sources, because F-Droid and Play builds are signed with different keys and mismatched signatures make the API silently fail.

2. **The `termux-api` package** inside Termux:
   ```bash
   pkg install termux-api
   ```

**Diagnostic checklist:**

1. **Check the CLI is installed:**
   ```bash
   command -v termux-notification
   ```
   - **Good result:** prints a path like `/data/data/com.termux/files/usr/bin/termux-notification`
   - **Bad result:** prints nothing. Run `pkg install termux-api` and try again.

2. **Fire a manual test:**
   ```bash
   termux-notification --title "Test" --content "Hello from Termux"
   ```
   A notification should appear in the Android shade within a second or two.
   - **If the command hangs with no output and no notification:** The **Termux:API app** is not installed (or is from a different source than Termux). Install it from F-Droid and try again.
   - **If it prints a permission error or nothing appears:** Grant notification permission (step 3).

3. **Grant notification permission (Android 13+):**
   Open Android **Settings → Apps → Termux:API → Notifications → Allow** (on some devices it's under **Settings → Apps → Special app access → Notifications**).

4. **Keep Fit-ingo alive for scheduled reminders:**
   Open Android **Settings → Apps → Termux → Battery → Unrestricted** (disable battery optimization). Fit-ingo's `start.sh` already takes a wake-lock, but aggressive battery savers can still kill the process.

5. **Test from the app itself:**
   In Fit-ingo, open **Settings → Reminders → Send test notification**. It reports whether the Termux:API CLI was detected and shows any error message.

**Note on Android 14+:** Some Termux:API command behavior changed due to Android permission changes, but basic `termux-notification` still works once permission is granted.

## Reminders don't fire at the set time

- The server must be running: `bash termux/start.sh` should show "Fit-ingo running at ...".
- Keep Termux in the background with its persistent notification visible.
- Reminders only fire on **scheduled training days** when that day's workout is **not yet done** — this is by design.
- Battery optimization is the usual culprit — see step 4 in the checklist above.

## The app won't load at http://localhost:8777

- Make sure `bash termux/start.sh` is running and shows "Fit-ingo running at ...".
- Use `http://localhost:8777` (not `https`).
- If the port is busy, set a different one:
  ```bash
  FITINGO_PORT=8778 bash termux/start.sh
  ```
