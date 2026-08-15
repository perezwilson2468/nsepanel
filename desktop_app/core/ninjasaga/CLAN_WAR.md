# NinjaSaga Clan War

## Goal
Implement desktop `NinjaSaga` Clan War around the official AMF flow, with a modal-based control panel instead of a plain action button.

## Current flow in the panel
1. Open Clan War modal
2. Load and cache:
   - `ClanService.getClanStatus`
   - `ClanService.getClan`
   - `ClanService.getWarList`
   - `ClanWar.getMemberList`
3. User chooses target clan from war list
4. User sets options:
   - auto spend token for stamina
   - bleeding mode
   - manual recruit
   - delay settings
5. If `Battle` is clicked:
   - if bleeding mode + manual recruit:
     - open recruiter popup
     - user selects up to 2 members
     - continue battle
   - otherwise:
     - continue directly
6. Start Clan War loop
7. Stop from the global `Stop Current Action` button or the clan-war stop endpoint

## Bleeding mode rule
Stop auto-recruiting after the first battle that gives any reputation.

## Official AMF calls used
- `ClanService.getClanStatus`
- `ClanService.getWarList`
- `ClanWar.getMemberList`
- `ClanWar.getBattleDefender`
- `ClanService.buyStamina`

## `ClanWar.getBattleDefender`
Official client call in `Panel/clan_panel.as`:

```as
ClanWar.getBattleDefender([
  session_key,
  updateSequence(),
  getHash(battleClanId + selectedMemberStr + session_key),
  battleClanId,
  battleClanName,
  selectedMemberStr,
  quickBattle,
  "",
  "9207082204942331"
])
```

### Current desktop implementation
The panel uses the quick-battle route only.

That means:
- `quickBattle = true`
- if response comes back with immediate result, we continue loop
- if response falls into manual/defender battle path, we stop safely and log it

## Modal behavior rules
- Opening modal loads clan data and keeps it cached
- Closing modal clears clan-war state if no clan-war task is running
- Global stop button can stop Clan War
- Clan War modal no longer owns the only stop path

## Delay settings
Current settings stored in modal state:
- `battle_delay_seconds`
- `refresh_delay_seconds`
- `buy_stamina_delay_seconds`
- `amf_call_delay_seconds`
- `post_captcha_resume_delay_seconds`

## Files
- `core/ninjasaga/clan_war.py`
- `main.py`
- `templates/index.html`

## Known limits
- Current implementation relies on quick-battle resolution via `ClanWar.getBattleDefender`
- If server returns defender/manual battle flow (`result == 1`), the loop stops instead of simulating the full fight
- Parsing of clan status / war list / member list is heuristic because decrypted AMF key names vary
- Post-captcha resume is still the main unstable area:
  - captcha can be solved inside the panel now
  - but the first resumed clan-war request may still hit an invalid-session state on some runs

## Next improvements
1. Capture the exact first `ClanWar.getBattleDefender` response after captcha solve when invalid-session happens
2. Support full manual defender battle flow if needed
3. Add a clearer reputation/stamina live summary in the modal while running
4. Tighten clan/member/prestige parsing if more decrypted samples become available

## Current Captcha Progress
The official client behavior in `Panel/clan_panel.as` is:

- detect `response.show_captcha`
- call `showWebView({"action":"show_captcha"})`

We first tried a native webview route, but the live site flow turned out to be more specific than that.

### What we found from the live site
- The official AIR shell loads:
  - `https://ninjasaga.cc/?minimal&air&noreauth=1`
- The live web app bundle uses:
  - `./api.php/custom-captcha/generate`
  - `./api.php/verify-captcha`
- The app always includes `uuid`
- Custom captcha verify sends:
  - `challenge_id`
  - `answer`
  - `hmac`
  - `mt` (mouse trail)

### Current desktop panel implementation
The panel now renders custom captcha directly inside the Clan War fullscreen screen instead of only showing instructions.

Supported challenge types:
- `grid_color`
- `slider`
- `drag_shape`
- `rotate`

Implemented files:
- `core/ninjasaga/amf_req.py`
- `main.py`
- `templates/index.html`

### Current in-panel flow
1. Clan War detects `show_captcha`
2. Clan War pauses and keeps waiting on the resume event
3. Panel opens the fullscreen captcha screen
4. Panel requests a live challenge from:
   - `/api/user/{user_id}/clan_war/captcha_challenge`
5. Backend proxies to NinjaSaga:
   - `api.php/custom-captcha/generate`
6. User solves the challenge inside the panel
7. Panel verifies through:
   - `/api/user/{user_id}/clan_war/captcha_verify`
8. Backend proxies to NinjaSaga:
   - `api.php/verify-captcha`
9. On success:
   - backend logs `Wait server captcha response...`
   - backend performs a silent NinjaSaga relogin using saved quick-login credentials
   - old Clan War worker is restarted silently
   - clan-war captcha state is cleared
   - a fresh Clan War worker resumes through the normal snapshot flow again
   - Clan War then continues attacking automatically

### Current verify payload
Current panel verify request to NinjaSaga contains:
- `challenge_id`
- `answer`
- `hmac`
- `mt`
- `uuid`

Notes:
- `uuid` is attached by the backend helper when forwarding to `api.php/verify-captcha`
- the panel no longer exposes a captcha refresh button, because replacing the generated challenge could break verification against the original server-side challenge
- if verify fails and the server says try again, the panel auto-loads a fresh challenge

## Official Client Findings About Post-Captcha Flow
- `Panel/clan_panel.as` sends `ClanWar.getBattleDefender(...)` with the normal AMF session key.
- In `gotDefender(response)` the official client:
  - subtracts clan stamina by 10 immediately
  - reads `result`, `prestige_gain`, `rep_gain`
  - if `response.show_captcha` is present, opens the webview with `showWebView({"action":"show_captcha"})`
- The ActionScript path does **not** show any AMF re-login or AMF session-key refresh at that point.
- This strongly suggests the captcha is a gate for **subsequent** clan-war requests, not a step that mutates the current AMF session key.

## Official WebView / AIR Findings
- `NinjaSaga.as` hosts the embedded web shell at:
  - `https://ninjasaga.cc/?minimal&air&noreauth=1`
- `showWebView({...})` sends a JS `parent.postMessage(...)` into that already loaded page.
- `hideWebView()` moves the webview off-screen and reloads the same AIR shell URL again.
- `handleNsDataUrl(...)` listens for webview callbacks like:
  - `nsdata://session_expired`
  - `nsdata://notloggedin`
  - `nsdata://error`
  - `nsdata://close_webview`
- On `session_expired/notloggedin/error`, the official client deletes webview cookies and reloads the AIR shell. This looks like **web session / cookie recovery**, not AMF session-key rotation.

## Source HTML Findings
- `NinjaSagaApk/source.html` contains the visible captcha host:
  - `<div id="hcaptcha-container" style="display: inline-block;"></div>`
- It also dynamically loads:
  - `./assets/js/app.js?v=...`
- The local workspace does not contain that built `assets/js/app.js` bundle, so the exact browser-side `postMessage({action:"show_captcha"})` success callback could not be traced locally from source files alone.

## `app.js` Findings About Captcha Success
- `NinjaSaga Game Client/Panel/app.js` listens for browser messages:
  - `window.addEventListener("message", ...)`
- When it receives:
  - `{ action: "show_captcha" }`
- it opens the captcha UI by calling:
  - `show_custom_captcha()` or `show_hcaptcha()`

### What happens after captcha verify succeeds
- For custom captcha, `app.js` calls:
  - `api_call(captcha_ep_verify, { challenge_id, answer, hmac, mt })`
- If the verify response is successful:
  - in AIR mode (`?air`) it does:
    - `window.location.href = 'nsdata://close_webview'`
- It does **not** send an AMF token back to the game.
- It does **not** show evidence of changing the AMF `session_key`.

### What AIR does with that success signal
- `NinjaSaga.as` handles:
  - `nsdata://close_webview`
- then calls:
  - `hideWebView()`
- and `hideWebView()` reloads the AIR shell URL again in the background:
  - `https://ninjasaga.cc/?minimal&air&noreauth=1`

This means the official success flow is effectively:
1. solve captcha in web layer
2. emit `nsdata://close_webview`
3. AIR hides webview
4. AIR reloads the minimal web shell again

### Why this matters
- The official client appears to refresh the **webview page state** after captcha success.
- It still does **not** show evidence of AMF session-key rotation.
- This supports the hypothesis that the fragile part after captcha is web anti-bot / cookie / page state, not the AMF key itself.

## Captcha Field-Diff Findings From Real AMF Captures
The user compared AMF responses before and after solving captcha, and we then decoded the hashed AMF keys/values using the panel's existing AES decryption in `core/ninjasaga/amf_req.py`.

### Confirmed decrypted field names
Decoded examples from the real payload:
- `a9de0e9ee76c8651ecf9aeb716d526f2` -> `status`
- `5e53876a16f9d0e22c8872e1bd17ae2b` -> `result`
- `26dc5939e573036bcc329245e35ce871` -> `server_time`
- `1e1e7bb359f7631573ee37b6842858d4` -> `clan_reputation`
- `f1059639f89fa79713c4ba42974f2e45dfa5d8da85f4e06d5aadb7e6a25e1813` -> `character_stamina`

Nested `getClan` fields decoded:
- `efc8b1f022fe3f2a782dd313e3b0ecff` -> `id`
- `e8d2d08a646e0a453568eb50fca037b1` -> `name`
- `8e67a6baea3c5009dd45fae6df69bd68` -> `master_id`
- `a4981a4737d4c9f648cb9eecf0632bfc` -> `master_name`
- `84a962e8be790f5974d1d43a6fbc1e36` -> `gold`
- `b07b0ce3bc489166f7218b8d37ebc889` -> `token`
- `13a5f6d6d268f369214109df41377cc6` -> `reputation`
- `963a27bc7b7e8b033c65ca2b92aa6f35` -> `prestige`
- `4ec27de4e80ea6dccb1de145cebe9067` -> `level`
- `12f83c22536bc1b3a0a3553d71836f01` -> `member_slots`
- `c7fed9c7f33da079ba3a1d236fb49999` -> `member_number`
- `63fc17f2a43392511580b7b534bc4296` -> `rank`
- `400f1199ff70726e28a6f5cd9f4328ba` -> `remaining_time`
- `1fcd5c5f4cf4e4fb42a29f453a474a4b00309e59a227bc1763872a6215b18375` -> `today_reputation`
- `d7de1f0f223db9f955568452df88f40c` -> `group_id`
- `4e5fd7fbf3af1cf64c0fd1f6bb1d9d34` -> `stamina_item`
- `8418c43763426002878df3adabb753fc242ca6bcdea0b4a8710de3edbd67c67a` -> `daily_reputation_show`

### `ClanService.getClanStatus`
- Before captcha and after captcha, the captured payload was effectively identical.
- This is a strong sign that captcha solve does **not** change the broad clan/account status snapshot in a visible way.
- It also weakens the idea that captcha solve rotates the main AMF session key.

### `ClanService.getClan`
The overall payload shape stayed the same, but several **decoded** fields changed after captcha.

Observed changed fields:
- `server_time`
  - before: `547677d30aa3198bbcea3d9c3d0a631e`
  - after:  `9539ee7ebd2e8b4bd10adb196aa19a01`
- `character_stamina`
  - before: `"200"`
  - after:  `"110"`
- `remaining_time`
  - before: `1149997`
  - after:  `1149769`

Observed stable fields:
- Most of the overall clan/member payload structure stayed unchanged.
- Clan identity-like values remained stable.
- `getClanStatus` remained unchanged.

### Practical interpretation
- `server_time` changing is expected and suggests a fresh server-side state snapshot.
- `remaining_time` changing is also expected and suggests the clan screen timer/state continues moving normally.
- `character_stamina` changing confirms real runtime state progressed across the captcha event.
- Together, these changes point to a **partial runtime refresh** after captcha, not a full AMF session replacement.

### Practical conclusion
- Captcha solve appears to update normal clan runtime values and timers.
- The main clan status snapshot does not visibly change.
- The evidence still supports the theory that the missing piece in the panel is a web-state / post-captcha transition, not simply "refresh AMF session key".

## Current Best Interpretation
- The official client behavior does **not** indicate that solving captcha changes the AMF `session_key`.
- The stronger hypothesis now is:
  1. `ClanWar.getBattleDefender` returns a real battle result and may also flag `show_captcha`
  2. the webview solves the captcha in the AIR shell
  3. the solve updates some **web anti-bot state / cookies / server-side gate**
  4. the next clan-war AMF requests are expected to work without changing the AMF key
- If captcha is not accepted, the webview likely answers with `nsdata://session_expired`, `nsdata://notloggedin`, or `nsdata://error`, and the client rebuilds the webview state by clearing cookies and reloading the AIR shell.

## Current Remaining Issue: Invalid Session After Solved Captcha
Current symptom:
- captcha solve completes in-panel
- panel returns to Clan War
- first resumed clan-war request can behave like invalid session

### Current working hypothesis
- The real client looks simple from Charles:
  - captcha verify succeeds
  - user continues battle
- The panel currently adds a **silent relogin** immediately after verify success, then silently restarts the Clan War worker.
- This is still a practical/debugging compromise and may differ from the lightest possible real-client flow.

### Fixes already applied
1. Removed challenge refresh from the captcha UI
- The panel now keeps the original generated challenge on screen
- This avoids breaking verify against a replaced server-side challenge

2. Verify now uses the same generated captcha state
- The panel sends the current challenge's `challenge_id`, `answer`, `hmac`, `mt`, and backend `uuid`

3. Post-captcha NinjaSaga relogin refresh
- After successful captcha verify, the backend refreshes NinjaSaga login state again
- updates:
  - `config.login_data`
  - `session.login_data`

4. Silent worker restart after captcha
- After captcha success, the old Clan War worker is stopped
- a fresh Clan War worker is started again
- this reduces stale in-memory state risk around the previous running worker

5. Better battle logging
- Clan War battle log now includes stamina left after each battle

6. Clan token uniq id now comes from the live SWF
- The panel no longer relies on a hosted JSON token source
- it downloads `clan_panel.swf`
- decompresses it
- extracts the current clan token uniq id from the SWF byte/string cluster near the captcha bridge
- if extraction fails, Clan War now raises:
  - `clan_token_uniq_id not found`

7. Low stamina without auto spend now stops immediately
- For NinjaSaga Clan War:
  - if stamina is below 10
  - and `Auto Spend Token` is disabled
  - the battle loop stops immediately
- The old low-stamina wait setting has been removed from the modal UI and backend settings shape

8. Clan War modal lifecycle cleanup
- Opening the modal the first time auto-loads clan data, so `Refresh` is not needed for first view
- `Refresh` is disabled while `/api/user/{user_id}/clan_war/open` is in flight
- captcha/open/start/poll responses now merge into existing modal state instead of overwriting the snapshot blindly
- this keeps clan data visible in the modal after captcha resume
- starting another normal action clears cached Clan War modal state
- logout also clears Clan War modal/captcha state

### What still needs investigation
- Whether the first resumed `ClanWar.getBattleDefender` requires more than a refreshed AMF session:
  - refreshed web cookie flag
  - post-captcha web token state
  - quick-battle state reset on target clan

### Best next debugging step
- capture/log the exact first resumed `ClanWar.getBattleDefender` response after captcha solve
- compare it with:
  - pre-captcha successful quick battle
  - post-captcha invalid-session failure

## Why we are not bypassing it
- The client explicitly expects a captcha solve path
- Skipping it risks fake results, no stamina consumption, or infinite loops
- The safe behavior is:
  - detect
  - pause
  - surface solve UI
  - resume only after the user completes the challenge
