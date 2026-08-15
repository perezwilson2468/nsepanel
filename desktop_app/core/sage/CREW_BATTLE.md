# Crew Battle Notes

This file tracks the current state of the desktop `Crew Battle` feature for base `Ninja Sage`, focused on the official server first.

## Current Status

Implemented on desktop:
- Action button added: `Crew Battle`
- Action registry entry added in `core/sage/actions.py`
- Official server support added via `crew_url` in `core/config.py`
- First working desktop implementation added in:
  - `core/sage/crew_battle.py`

Current runtime behavior:
- Official server only
- Authenticates with official crew service
- Loads crew info
- Loads stamina / phase
- Automates `phase 2` castle attacks
- Repeats while stamina is available
- Waits for stamina recovery when stamina is below `10`

Current limitation:
- `phase 1` is **not automated yet**
- If current season is in phase 1, the action logs that phase 1 is not automated yet and exits cleanly

## Official Client Findings

Source files used:
- `android_app/crew.as`
- `android_app/crewbattle.as`
- `NinjaSaga Game Client/code library/ninjasaga/Battle.as`

### Crew HTTP service

Official client uses a separate HTTP service, not AMF, for the main crew feature.

Base URL from client:
- `https://crew.ninjasage.id`

Observed endpoints from `crew.as`:
- `/auth/login`
- `/player/crew`
- `/player/stamina`
- `/battle/opponents`
- `/battle/castles/`
- `/battle/castles/{id}`
- `/battle/phase1/start`
- `/battle/phase2/start`
- `/battle/phase1/finish`
- `/battle/phase2/finish`
- `/battle/castles/{id}/defenders`
- `/battle/castles/{id}/ranks`
- `/battle/attackers`

### Phase 1 start payload

From `crewbattle.as`:

```text
{
  "b": random 22-char string,
  "c": selectedCastle + 1,
  "t": current time in ms,
  "f": recruited friend ids,
  "e": selected boss id,
  "h": md5(char_id|b|t|c|e)
}
```

Notes:
- phase 1 opens full combat flow
- recruited friends can be selected
- selected boss comes from crew boss data in `gamedata.json`

### Phase 2 start payload

From `crewbattle.as`:

```text
{
  "c": castle_id,
  "b": random 24-char string,
  "t": current unix time in seconds,
  "h": md5(char_id|b|t|c)
}
```

Phase 2 returns a direct quick-battle style result payload in the client UI, which is why it is the first part implemented in desktop panel.

### Battle finish path found in client

Important finding from `Battle.as`:
- Crew battle finish is submitted through AMF method:
  - `CrewWar.finishLandHunt`

Observed AMF call signatures:

Phase 1 / win flow:

```text
CrewWar.finishLandHunt(
  session_key,
  itemUsedInBattle,
  recruitedMembers.toString(),
  selectedNewClanWar,
  0,
  updateSequence(),
  ClanWarHash,
  battleFlowLogver,
  startBattleId,
  jsonStr2,
  hash
)
```

Phase 2 / quick-battle style:

```text
CrewWar.finishLandHunt(
  session_key,
  itemUsedInBattle,
  recruitedMembers.toString(),
  selectedNewClanWar,
  1,
  updateSequence(),
  ClanWarHash
)
```

## What We Still Need To Finish It Properly

To implement both phase 1 and phase 2 cleanly, we still need real official request/response captures for the dynamic values the UI code does not fully explain.

Most important missing pieces:

1. Official HTTP response samples
- `/auth/login`
- `/player/crew`
- `/player/stamina`
- `/battle/castles/`
- `/battle/phase1/start`
- `/battle/phase2/start`

2. Real `CrewWar.finishLandHunt` captures
- one successful phase 1 finish
- one successful phase 2 finish

3. Confirmed meaning of runtime fields
- `selectedNewClanWar`
- `recruitedMembers.toString()`
- `itemUsedInBattle`
- `updateSequence()`
- `battleFlowLogver`
- `startBattleId`
- `jsonStr2`
- `hash`

## Best Data To Capture Later

When we return to this feature, capture these exact requests:

1. `/auth/login`
2. `/player/crew`
3. `/player/stamina`
4. `/battle/phase1/start`
5. `/battle/phase2/start`
6. `CrewWar.finishLandHunt` for phase 1
7. `CrewWar.finishLandHunt` for phase 2

Best format:
- request body
- response body
- any relevant headers
- whether it was phase 1 or phase 2
- whether it was win/lose

## Practical Next Step Later

When we resume:

1. Finish official phase 2 more completely if needed
- optional defender/target selection
- optional better castle selection policy

2. Implement official phase 1
- reproduce start payload
- reproduce battle finish submit through `CrewWar.finishLandHunt`
- preserve official battle log/hash fields

3. Only after official is stable:
- add Android support
- add per-server variants

## Related Files

- `core/sage/crew_battle.py`
- `core/sage/actions.py`
- `core/config.py`
- `templates/index.html`
- `android_app/crew.as`
- `android_app/crewbattle.as`
- `NinjaSaga Game Client/code library/ninjasaga/Battle.as`
