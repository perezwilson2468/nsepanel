# NinjaSaga Progress Log

This file tracks what we have achieved in the NinjaSaga integration and where we left off.

## What We Achieved

1. Separated NinjaSaga flow from other games
- NinjaSaga action routing is isolated (`core/ninjasaga/actions.py` + `core/action_router.py`).
- NinjaSaga-specific login/session/protocol handling is independent.

2. AMF/login flow mapped and stabilized
- `SystemService.requireLogin`
- `SystemService.snsLogin`
- `SystemService.checkAmf`
- `CharacterDAO.getCharactersList`
- Character select/get data flow fixed for list/dict response variants.

3. Encryption/decryption handling improved
- Decryption cleanup for malformed control/padding characters.
- Debug output added for NinjaSaga protocol tracing.
- UI can show decrypted/logged flow through runtime logs.

4. Leveling loop implemented
- Auto mission start + update character progress cycle.
- Uses updateCharacter payload first, fallback refresh only when needed.
- Prints live progress: name, level, rank, XP, gold (and energy when available).

5. Rank/mission behavior tuned
- C/B/A pools synced with extracted client data.
- Rank caps and gating logic added.
- Level-gated mission handling and fallback behavior improved.

6. Anti-detection profile added
- Centralized profile in `core/config.py`.
- Runtime controls for delay/jitter/rest/backoff/circuit-breaker.
- Cloudflare/rest handling with clearer cooldown behavior.

7. Stop action behavior improved
- Stop now shows clearer "stopping" state in backend + UI.
- UI badge/status reflects stopping vs running.

8. NinjaSaga settings panel added (UI)
- NinjaSaga-only settings API:
  - `GET /api/settings/ninjasaga`
  - `POST /api/settings/ninjasaga`
- Sidebar now has compact `NinjaSaga Settings` button.
- Settings panel supports Indonesian/English tooltips via `?` help icons.

9. Auto-spend settings model (scaffold)
- Trigger energy is fixed to `0`.
- Refill amount treated as automatic full refill.
- User sets max full refills per run.
- Token cost follows server rules (not manually entered).

10. Easter Event automation implemented
- `EasterFestival2015.getBattleStatus` parsing + loop is active.
- Chest-first pathing implemented; empty-tile movement is local (no AMF call).
- `EasterFestival2015.startBattle` + fixed 25s wait + `ItemDAO.getBossReward` finish flow implemented.
- Finish payload uses observed winning format first (`result=0`, default battle log), with fallback.
- Character refresh runs after boss finish to sync level/xp/gold in panel logs.
- Boss/enemy names mapped from `NinjaSaga Game Client/Panel/alldata.as` (`enemy390..enemy419`).
- AMF pacing/retry added for Easter calls (min gap + jitter + error 100 retry).

11. Event-panel auto-spend UI moved and wired
- NinjaSaga auto-spend controls moved to Events panel above `Easter Event`.
- Default remains disabled.
- Uses existing NinjaSaga settings API/state (`/api/settings/ninjasaga`).
- Supports quick save from event panel and full save from settings modal.

12. Easter auto-spend runtime implemented
- If hearts reach `0` and auto-spend is enabled, panel buys battle hearts automatically.
- Refill amount follows client constraints (up to 3 per buy call), repeated until target/full.
- Stops at user-defined `max_refills_per_run`.
- Refreshes status after buy to confirm current hearts before continuing.

13. Refactor pass completed (safe split)
- Shared modules added to reduce monolithic logic in `leveling.py`:
  - `core/ninjasaga/mission_policy.py`
  - `core/ninjasaga/anti_detection.py`
  - `core/ninjasaga/rate_control.py`
  - `core/ninjasaga/recovery.py`
  - `core/ninjasaga/progress_parser.py`
- `leveling.py` now delegates mission policy, rate control, recovery/relogin, and progress parsing to shared components.
- Mission picking is metadata-driven and filtered by:
  - required level
  - `daily=false`
  - non-empty grade
  - reward not both zero (`xp/gold`)
  - premium eligibility by account type.

14. Recovery/relogin extended to other NinjaSaga actions
- `eudemon.py` now handles runtime exceptions with shared recovery policy:
  - Cloudflare rest/backoff reaction
  - relogin + reselect character recovery path
- `easter.py` now attempts shared recovery on AMF failures for:
  - `getBattleStatus`, `openTreasure`, `startBattle`, `finishBossReward`, `generateNewMap`, and buy-heart flow.
- Easter now avoids pointless movement when heart is `0` and no adjacent chest is available.

15. Rank-exam expansion + mode setting
- Leveling now supports automatic rank exams beyond Jounin:
  - Special Jounin exam at level cap 60
  - Tutor exam at level cap 80
- Added mission sets from client `Data.as`:
  - `EXAM_SPECIAL_JOUNIN_ARR` + `_EASY`
  - `EXAM_SENNIN_ARR` + `_EASY` (used as Tutor exam flow)
- Added desktop NinjaSaga setting `exam_mode` (`easy`/`hard`) via:
  - `GET /api/settings/ninjasaga`
  - `POST /api/settings/ninjasaga`
- Added `Exam Mode` selector in NinjaSaga settings modal (`templates/index.html`).

## Current Working State

- Login, character listing, character selection, and dashboard flow are working.
- NinjaSaga leveling runs in cycle with anti-detection timing controls.
- Runtime settings can be changed from UI without editing code files.
- Stop action is more reliable and gives user feedback.
- Easter event automation is runnable end-to-end (status, chest, move, battle, finish, refresh).
- Easter auto-spend works with per-run limit from UI settings.
- Shared recovery path is active for leveling, eudemon, and easter actions.

## Where We Left Off

1. Cloudflare/gateway blocks still possible
- We handle it with rest/backoff/circuit-breaker.
- No bypass/impersonation logic is implemented (intentionally).

2. Easter pathfinding can be improved further
- Current pathing is greedy/local (adjacent chest first).
- Optional upgrade: shortest-path target selection (nearest chest/boss by Manhattan path) with obstacle awareness.

## Next Steps

1. Easter auto-spend runtime status in UI
- Implemented in Events panel:
  - `Status`
  - `Refills used / max`
  - `Last result/message`
- Values are fed from backend runtime state (`ninjasaga_state.easter_auto_spend_runtime`) via `/api/user/{id}/status` polling.

2. Optional pathfinding upgrade for Easter board
- Improve move decision to pick shortest route to nearest valuable target.

3. Add small integration tests/smoke scripts
- Implemented `core/ninjasaga/smoke_tests.py` with basic local checks for:
  - mission picker + eligibility filters
  - progress parser extraction
  - recovery/rate helper glue
- Run with: `python -m core.ninjasaga.smoke_tests`

## Key Files

- `core/ninjasaga/amf_req.py`
- `core/ninjasaga/leveling.py`
- `core/ninjasaga/actions.py`
- `core/ninjasaga/bootstrap.py`
- `core/config.py`
- `main.py`
- `templates/index.html`
- `core/ninjasaga/CLIENT_NOTES.md`
