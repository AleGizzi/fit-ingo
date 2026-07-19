# fit-ingo

Local-first, Duolingo-style fitness PWA. Single user, no accounts, no cloud — all data lives in one SQLite file on device. Runs on a PC for development and self-hosts on Android via Termux.

## Shape

- **`server/`** — Flask + SQLite. `app.py` (routes, entry) · `db.py` (schema + migrations) · `reminders.py` (on-device notification thread) · `seed/exercises.json` (exercise catalog, loaded on first run) · `tests/`
- **`frontend/`** — React + Vite PWA, TypeScript, i18next (en/es). Entry `src/main.tsx`.
- **`termux/`** — Android hosting: `setup.sh`, `start.sh`, boot hooks. See `termux/TROUBLESHOOTING.md` when notifications misbehave.
- **`tools/uicheck/`** — UI screenshot utilities.

## Commands

```bash
# backend
python -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt   # from server/
python app.py                # :8777
python -m pytest             # planner, diet, streak logic

# frontend
npm install
npm run dev                  # :5173, proxies /api → :8777
npm run build                # → frontend/dist/
npm run lint
```

## Data model

Schema is defined in **`server/db.py`** (the `CREATE TABLE` block) — that file is the source of truth, and schema version is tracked in the `meta` table for migrations. SQLite runs in WAL mode with foreign keys on.

Tables: `meta` · `profile` (single row, id=1) · `exercises` (seeded from JSON) · `plan` → `plan_days` → `plan_items` (the generated program, three levels) · `workout_log` (one row per date, UNIQUE) · `weight_log` (one row per date, UNIQUE) · `settings` (single row, id=1)

Read `db.py` before writing any query — several columns are JSON blobs (`limitations`, `muscle_groups`, `contraindications`, `items_done`, `reminder_times`), not scalars.

## Config

| Var | Default | What |
|---|---|---|
| `FITINGO_PORT` | `8777` | Backend port |
| `FITINGO_DB` | `server/data/fitingo.db` | SQLite path (Termux: `~/fit-ingo/data/fitingo.db`) |

PWA config is in `frontend/vite.config.ts` — `vite-plugin-pwa`, autoUpdate, app shell offline, `/api/*` cached NetworkFirst with a 3s timeout.

## Gotchas

- **`frontend/dist/` is committed on purpose.** Termux pulls the built app so Android doesn't need Node. After any frontend change you must `npm run build` **and commit dist/**, or the phone silently keeps serving the old UI.
- **Releases bump `frontend/src/lib/version.ts`** (+ a `CHANGELOG.md` entry). Settings ▸ Check for updates reports that constant, so shipping without bumping it makes the phone claim it's up to date when it isn't.
- **All DB access goes through `db.get_conn()`, which is per-thread.** Never cache a connection at module level or pass one between threads — sharing one across Flask's request threads and the reminder thread interleaves cursors and makes reads return phantom empty rows (see `tests/test_concurrency.py`).
- **Changing the profile wipes history.** `server/app.py` regenerates the plan and clears workout + weight logs on profile update. That's intended, but it means profile edits are destructive — confirm with the user before triggering one.
- **Reminders only work on-device.** The scheduler matches wall-clock time and only fires on training days with an incomplete workout; on a PC it logs to console instead of notifying.
- **Termux:API needs matching sources** — the Termux:API *app* and the `termux-api` *package* must both come from F-Droid or both from Play. Mixed sources fail silently. See `termux/TROUBLESHOOTING.md`.
- **Android battery optimization must be disabled for Termux**, or the reminder thread gets killed.
