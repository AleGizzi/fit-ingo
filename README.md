# Fit-ingo 🔥

A Duolingo-style fitness PWA. It builds a personalized workout program from your
age, size, goal, fitness level, impact tolerance and equipment, then nudges you
with daily reminders to keep your streak alive. Each exercise links to a YouTube
how-to and a short explanation. It tracks your progress and suggests meals.

**Everything runs on your own device. Your data never leaves it — no accounts,
no cloud, no subscriptions.**

- Personalized weekly plan (warm-up → workout → cool-down), no/low/normal impact
- Duolingo-style streaks with a week ring and streak-saver nudges
- Daily reminders via local Android notifications (Termux:API) — no Google/FCM
- Exercise catalog with YouTube links (editable) and simple instructions
- Progress metrics: streak, completion, weight trend, 12-week consistency
- Diet targets (calories/macros) + daily meal ideas, vegetarian-aware
- Dark / light theme, English / Spanish
- Installable PWA, works offline

## Architecture

```
Android phone
├── Chrome (installed PWA)  ── http://localhost:8777 ──┐
├── Termux                                             │
│   ├── Flask server (serves the PWA + JSON API) ◄─────┘
│   ├── SQLite  (~/fit-ingo/data/fitingo.db)
│   └── reminder thread → termux-notification
└── Termux:Boot (optional) → auto-starts on reboot
```

- **`server/`** — Flask + SQLite. Pure Python, installs cleanly in Termux.
- **`frontend/`** — React + Vite PWA. Built on a computer; Termux only serves the
  static `dist/` (which is committed, so the phone never needs Node).

## Run it on Android (Termux)

1. Install **Termux**, **Termux:API**, and (optional) **Termux:Boot** from
   [F-Droid](https://f-droid.org). The Play Store builds are outdated — use F-Droid.
2. Clone this repo in Termux, e.g. into `~/fit-ingo-app`:
   ```bash
   pkg install git
   git clone <your-repo-url> ~/fit-ingo-app
   cd ~/fit-ingo-app
   ```
3. One-time setup and start:
   ```bash
   bash termux/setup.sh
   bash termux/start.sh
   ```
4. Open **Chrome** at <http://localhost:8777>, then menu → **Add to Home screen**.
   Launch it from the home screen for the full-screen app.
5. In the app: finish onboarding, then **Settings → Reminders** to set your times.

### Updating

```bash
bash termux/update.sh
```

Pulls the latest version, syncs Python deps, and restarts the server. Then open
the app, close it, and reopen — the service worker swaps to the new build in the
background (**Settings → Version** shows what's running; **Check for updates**
forces the swap).

**Make reminders reliable:** Android → Settings → Apps → Termux → Battery →
allow unrestricted / disable optimization. `start.sh` already takes a wake-lock.
Keep Termux running in the background (its persistent notification).

### Watch / fit-band data (optional)

**Progress → Watch & band data → Import .FIT files.** Fit-ingo reads the
`.FIT` files Garmin watches and most fit bands record — activities (sport,
duration, distance, heart rate, calories) and daily wellness (steps, resting
HR) — and charts them. Getting the files, fully offline:

- **USB**: plug the watch into a computer (or the phone with OTG) — activity
  files live in `GARMIN/Activity/`, daily wellness in `GARMIN/Monitor/`.
- **Garmin Connect** (if you use it): every activity page has
  *Export Original* → a `.zip` with the `.FIT` inside.

Parsing happens on-device (`fitdecode`, pure Python); nothing is uploaded
anywhere. Re-importing the same files is safe — duplicates are skipped.

No watch? A phone by itself counts steps (Google Fit / any pedometer app uses
the accelerometer), but there's no export path from those apps into Fit-ingo
yet, and a phone has no heart-rate sensor — Google Fit's camera trick gives
only spot readings. Continuous HR needs a band/watch.

### Notifications not working?

Both the **Termux:API app** (installed from the same source as Termux — F-Droid or Play, not mixed) and the **`termux-api` package** (`pkg install termux-api`) are required. Android 13+ also needs notification permission granted to Termux:API in Settings. Try the in-app **Settings → Send test notification** button, and see `termux/TROUBLESHOOTING.md` for full diagnostics.

**Auto-start on reboot (optional):** see `termux/boot/fit-ingo.sh`.

## Develop on a computer

Requires Node 18+ and Python 3.10+.

```bash
# Backend (terminal 1)
cd server
python -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt
../.venv/bin/python app.py            # http://localhost:8777

# Frontend with hot reload (terminal 2)
cd frontend
npm install
npm run dev                           # http://localhost:5173, /api proxied to :8777
```

Without `termux-notification` present, reminders are logged to the console
instead of shown — so the whole flow is testable off-device.

### Build the PWA (do this before committing / deploying to the phone)

```bash
cd frontend
npm run build      # outputs frontend/dist/, which Flask serves
```

The `dist/` folder is committed so Termux can run `git pull` and never needs Node.
After changing frontend code, rebuild and commit the new `dist/`.

## Tests

```bash
cd server
../.venv/bin/python -m pytest        # planner, diet, and streak logic
```

## Customizing exercises & videos

The catalog lives in `server/seed/exercises.json` (bilingual, tagged by muscle
group, type, impact, difficulty, equipment and contraindications). Video links
default to a YouTube search for the exercise; the most common moves point at a
specific tutorial. You can also fix any link in-app from the workout screen —
edits are saved to your database and survive catalog updates.

## Privacy

There is no backend service and no telemetry. All data lives in a single SQLite
file on your device (`~/fit-ingo/data/fitingo.db`). To back it up, copy that file.
To wipe everything, delete it. The diet suggestions are general guidance, not
medical advice.
