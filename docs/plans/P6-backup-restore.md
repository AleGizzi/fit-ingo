# P6 — Backup / restore + nightly local snapshots

**Model: sonnet · Backend + Settings UI · Data-integrity critical**

## Objective

Local-first must not mean fragile: one-tap export of the whole database,
restore from a file, and automatic nightly snapshots with rotation.

## Files touched

- `server/app.py` (2 endpoints), `server/db.py` (snapshot helper),
  `server/reminders.py` (nightly hook in `_tick` — see below)
- `server/tests/test_backup.py` (new)
- `frontend/src/pages/Settings.tsx` + `settings.css`,
  `frontend/src/lib/api.ts`, i18n en/es

## Backend

### Snapshot helper (db.py)
```python
def snapshot_to(path: Path) -> None:
    """Consistent copy while WAL is active — sqlite3 backup API, never
    shutil.copy (WAL would tear)."""
    dest = sqlite3.connect(str(path))
    with _lock:
        get_conn().backup(dest)
    dest.close()
```

### `GET /api/backup`
Snapshot to a temp file in the DB's directory, then `send_file` as
`fitingo-backup-YYYYMMDD-HHMM.db` (`as_attachment=True`,
`application/octet-stream`); delete the temp file after (send_file +
`try/finally` or `after_this_request`).

### `POST /api/restore`
Multipart, field `file`. Steps, in order — abort on any failure with a JSON
error and the live DB untouched:
1. Save upload to `<db_dir>/restore-incoming.db`.
2. Validate: open read-only (`file:...?mode=ro`), `PRAGMA integrity_check`
   == "ok", and required tables exist (`profile`, `settings`, `workout_log`,
   `exercises`). Reject anything else (413/400 with reason).
3. Snapshot the current DB to `<db_dir>/pre-restore-<ts>.db` (safety net).
4. Swap: close ALL per-thread connections — you cannot enumerate other
   threads' `_local.conn`s, so instead: take `db._lock`, `get_conn().close()`
   for the current thread, `os.replace(incoming, db_path())`, then reset
   `db._local = threading.local()` and `db._schema_ready = False` so every
   thread lazily reopens against the new file. Document this in a comment —
   it is the one place allowed to touch those module internals.
5. Run `get_conn()` (triggers `_migrate` if the backup is an older schema —
   this must work; test it).
6. Return `{"ok": true}`; frontend does a full reload.

### Nightly snapshot
In `ReminderScheduler._tick` (it already runs every 30 s): once per day at
`03:00`–`03:05` window (dedup with the existing `_fired` mechanism, kind
`"backup"`), call `db.snapshot_to(<db_dir>/backups/fitingo-YYYYMMDD.db)`
(mkdir ok) and prune to the newest 7 files. Wrap in try/except — a failed
backup logs, never kills the thread.

## Frontend (Settings)

New card between "Version" and "Reset app":
- **Download backup** button → plain `<a href="/api/backup" download>` (no
  fetch needed; keeps memory flat).
- **Restore from backup** → hidden file input (`.db`) → confirm dialog
  (reuse `.confirm-sheet` styling): body warns it replaces ALL current data
  → `api.restoreBackup(file)` → on ok, `window.location.reload()`.
- Caption: `t("backup.help")` — mentions the automatic nightly snapshots and
  where they live (`data/backups/` next to the database).
- i18n: `backup.title`, `backup.download`, `backup.restore`,
  `backup.confirmTitle`, `backup.confirmBody`, `backup.help`,
  `backup.invalid` (server error passthrough is fine as detail).

## Tests

1. `GET /api/backup` returns a valid sqlite file (open it, check tables,
   check a seeded profile row survives the round trip).
2. Restore happy path: seed DB A (profile "Alice"), back it up, mutate live
   DB to "Bob", restore the backup → `GET /api/profile` says Alice; water &
   logs from A intact.
3. Restore rejects: (a) random bytes, (b) valid sqlite missing `profile`
   table. Live DB unchanged after both.
4. Restore of a schema-v2 backup migrates to current version on first read.
5. Snapshot prune keeps exactly 7 newest (unit-test the prune function).
6. Concurrency guard: run the existing `test_concurrency.py` suite after a
   restore in the same process (connections must have re-opened cleanly).

## Verify

Standard commands + paste test output. Playwright: click Download backup
(assert a download event fires with .db suffix), then restore flow against
a file produced by the test server; app reloads to the restored profile.

## Acceptance

All 6 tests green; a failed restore can never leave the app without a
working DB (prove via test 3); nightly snapshot code path exercised by
calling `_tick` with a fake 03:00 `datetime` in a unit test.
