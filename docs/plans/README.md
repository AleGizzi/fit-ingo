# Fit-ingo roadmap — agent work packets

Ten self-contained packets (P1–P10) covering the full 1.3.0 review feedback:
guided workouts, streak freezes, progression visibility, history, swap,
adaptive difficulty, backup/restore, notification upgrades, haptics, live
Bluetooth HR, exercise illustrations, and the tech-debt items.

Each packet is written so a single agent session can execute it **alone**:
context, exact files, frozen contracts, steps, acceptance criteria, and the
verification commands to run. Read this README first, then only your packet.

## Release grouping & execution order

| Release | Packets (in order) | Theme |
|---|---|---|
| v1.4.0 | P1 → P2 → P3 → P4 → P8 | Core experience: guided training, fair streaks, visible progress |
| v1.5.0 | P5 → P6 → P7 | Smart + resilient: swap/adaptive, backup, notification upgrades |
| v1.6.0 | P9 → P10 | Hardware + art: live HR, illustrations |

P1 **must land first** (schema v3 + contracts used by P2/P5/P7/P9).
Within a release, packets are ordered to avoid same-file collisions —
do not run two packets concurrently if they share files (see each packet's
"Files touched").

## Model routing

| Packet | Model | Why |
|---|---|---|
| P1 data & migrations | sonnet | precise, mechanical, contract-critical |
| P2 streak freezes | **opus** (or strong sonnet) | subtle state semantics; easy to get wrong |
| P3 guided workout | sonnet | large but well-specified frontend build |
| P4 progress/history/rest-day | sonnet | straightforward UI + one endpoint |
| P5 swap + adaptive | **opus** (or strong sonnet) | planner reasoning, fairness rules |
| P6 backup/restore | sonnet | careful but fully specified |
| P7 notifications | sonnet | shell-quoting care, otherwise mechanical |
| P8 haptics | haiku/sonnet | trivial |
| P9 Web Bluetooth HR | sonnet | spec-driven; hardware verify deferred |
| P10 illustrations | sonnet loop | volume work against a strict art spec |

The orchestrator (opus session with full context) assigns packets, reviews
every diff, runs integration QA, and owns version bumps, CHANGELOG, and
commits. **Worker agents do not commit or push.**

## Global rules (every packet inherits these)

1. **Fully local. No cloud calls, no accounts, no new network dependencies.**
2. **New Python deps** only if pure-Python (must pip-install inside Termux).
   Frontend: no new npm deps without orchestrator sign-off.
3. **EN/ES parity is a hard gate.** Every user-facing string goes in both
   `frontend/src/i18n/en.json` and `es.json`. Check:
   ```bash
   cd frontend && node -e "const en=require('./src/i18n/en.json'),es=require('./src/i18n/es.json');const f=(o,p='')=>Object.entries(o).flatMap(([k,v])=>typeof v==='object'?f(v,p+k+'.'):[p+k]);const a=f(en).sort(),b=f(es).sort();console.log(a.length===b.length&&a.every((k,i)=>k===b[i])?'OK':'MISMATCH')"
   ```
4. **DB access only via `db.get_conn()`** (per-thread connections). Never
   cache a connection or share one across threads. Multi-statement writes go
   inside `with db._lock:`. See `server/tests/test_concurrency.py`.
5. **Schema changes**: bump `SCHEMA_VERSION` in `server/db.py`, add both the
   `CREATE TABLE` (new DBs) and the `_migrate()` branch (existing DBs), and a
   migration test like `test_v1_db_migrates_in_place`.
6. **Strict TypeScript** — `npm run build` runs `tsc -b`; zero errors allowed.
7. **After frontend changes**: `cd frontend && npm run build` (dist/ is
   committed on purpose — Termux serves it without Node). The orchestrator
   commits dist.
8. **Verification is not optional.** Run the commands in your packet's
   "Verify" section and paste real output in your report. Never claim an
   unchecked pass.
9. **This machine**: IPv6 is broken — always `127.0.0.1`, never `localhost`,
   in scripts/tests. QA servers: `FITINGO_DB=<scratch>/qa.db FITINGO_PORT=8794`.
   Screenshots: `tools/uicheck/` (Playwright, viewport 402×874).
10. **Do not touch** `termux/setup.sh`'s commented-out pip upgrade line,
    the strict-streak semantics (outside P2's explicit changes), or the
    "profile change wipes activity" behavior.
11. Design language: ember `#FF5A1F`, violet `#6C4BF4`, mint `#00C48C`,
    gold `#FFB020`; chunky pressable buttons; both themes must look right
    (`data-theme` on `<html>`). Match existing CSS in `frontend/src/pages/`.

## Definition of done (per packet)

- All acceptance criteria demonstrably met (output pasted).
- `cd server && ../.venv/bin/python -m pytest -q` → all green, new tests added.
- `cd frontend && npm run build` → clean; parity check → OK.
- No files outside the packet's "Files touched" list modified (ask the
  orchestrator if you believe you must).
- A short handoff report: what changed, what to QA by hand, any deviations.
