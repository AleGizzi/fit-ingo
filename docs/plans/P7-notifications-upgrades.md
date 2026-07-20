# P7 — Notification upgrades: weekly recap, water action buttons, heartbeat (requires P1)

**Model: sonnet · reminders.py-centric · Mind the shell quoting**

## Objective

Three additions to the reminder thread: a Sunday recap, actionable water
notifications (+250 ml from the notification shade), and a visible
scheduler heartbeat so silent death is diagnosable.

## Files touched

- `server/reminders.py`, `server/app.py` (status endpoint + recap data fn)
- `server/tests/test_reminders_extra.py` (new)
- `frontend/src/pages/Settings.tsx` (recap toggle + heartbeat line),
  `frontend/src/lib/types.ts` (settings + status types), i18n en/es

## 1. Weekly recap

- Fires Sundays at 19:00 (fixed time, not configurable — keep it simple),
  kind `"recap"`, dedup via existing `_fired`, gated on P1's
  `settings.weekly_recap_enabled`.
- Content is built by a callback `get_recap()` injected like the other
  callbacks (app.py implements it): completed workouts this ISO week vs
  scheduled, current streak, liters of water this week (sum water_log
  Mon–today). Message templates in `MESSAGES` both languages, e.g. EN:
  `"This week: {done}/{planned} workouts · {liters} L water · streak {streak} 🔥"`.
- Recap fires even on rest days and when workouts are done (it's a summary,
  not a nag) — do NOT put it behind the training-day/is-done guards; give it
  its own `_tick_recap` like `_tick_water`.

## 2. Water notification action buttons

In `send_notification`, add optional `buttons: list[tuple[label, shell_cmd]]`
(max 3, termux limit). For the water nag in `_tick_water`, pass:

```python
buttons=[("+250 ml", f"curl -s -X POST -H 'Content-Type: application/json' "
                     f"-d '{{\"delta_ml\":250}}' http://localhost:{port}/api/water")]
```

- termux flags: `--button1 <label> --button1-action <cmd>`. The action runs
  in Termux's shell — `curl` is available (document: `pkg install curl` goes
  into `termux/setup.sh`'s pkg install line — add it there).
- Port must come from `FITINGO_PORT` env (default 8777) — thread it into
  reminders via a module constant read at import from `os.environ`, replacing
  the hard-coded `APP_URL` while you're there.
- Dev stub path (`termux=False`): log the buttons too so tests can assert.

## 3. Scheduler heartbeat

- `reminders.py`: module var `last_tick: str | None`, set at the top of
  every `_tick` (isoformat). Include in `get_status()` as `"last_tick"`.
- Settings UI: under the existing termux status line, show
  `t("settings.schedulerOk")` ("Reminder engine: active") when
  `now - last_tick < 120 s`, else `t("settings.schedulerStale")`
  ("Reminder engine: not running — restart the app in Termux") in warn
  color. Types updated in `types.ts`.

## i18n

`settings.weeklyRecap` ("Weekly recap (Sundays)"), `settings.schedulerOk`,
`settings.schedulerStale` — EN + ES. Recap message strings live server-side
in `MESSAGES` (both languages there, not in the frontend).

## Tests

1. `water_slots` untouched; new: `_tick_recap` fires exactly once on a fake
   Sunday-19:00 `datetime`, not on Monday, not when disabled.
2. Recap message renders from a seeded fixture (2/3 workouts, 3.5 L,
   streak 4) in both languages.
3. `send_notification` stub path records button labels; real path arg list
   contains `--button1` (assert via monkeypatched `subprocess.run`).
4. Heartbeat: after a manual `_tick`, `get_status()["last_tick"]` is fresh.
5. Water nag carries the button; workout reminder does not.

## Verify

Standard commands. Manual curl: `GET /api/notifications/status` shows
`last_tick` moving between calls ~30 s apart on a running QA server (or
call `_tick` directly). Screenshot Settings showing the heartbeat line.

## Acceptance

5 tests green; recap respects the toggle; `termux/setup.sh` installs curl;
no change to existing reminder/nag behavior (old tests green).
