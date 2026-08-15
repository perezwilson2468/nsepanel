# NinjaSaga Client Flow Notes

These notes are extracted from the decompiled files in `NinjaSaga Game Client/`.

## Known endpoints and methods

- AMF gateway in client:
  - `Data.AMF_SERVER = "https://amf.ninjasaga.cc/"`
- Login menu call:
  - `SystemService.login([username, password, Data.BUILD_NO])`
- Character list call:
  - `CharacterDAO.getCharactersList([Account.getAccountSessionKey()])`
- Character detail call:
  - `CharacterDAO.getCharacterById([Account.getAccountSessionKey(), charId])`
- System data call after character selection:
  - `SystemData.get([Account.getAccountSessionKey(), Data.TEST_VERSION])`

## Important encryption/signature clue

- `NinjaSaga.as` loads:
  - `swf/library/code_library.swf`
  - `swf/library/network_library.swf`
- Login hash generation references hidden codec value:
  - `this.codeLibrary.codec`
  - `Central.main.getLoginHash(...)`
- This indicates part of the real auth/signature flow is inside loaded SWFs that are not yet mapped in the Python panel.

## Extracted from provided library sources

- `code library/ninjasaga/linkage/CodeLibrary.as`:
  - `codec = "85224034668"`
- `code library/bitemycode/net/zendamf/ZendAMFClient.as`:
  - response values/keys can be encrypted hex strings.
  - decryption uses AES-ECB with a derived key truncated to 16 bytes.
  - derived key prefix (16 bytes) resolves to:
    - `K~5:Gt2[.,s$In=Z`
- `_downloaded/client_library.swf` string table:
  - contains `ClientLibrary` class and methods:
    - `encrypt`, `getLoginHash`, `generateHash`, `getHash`, `getArrayHash`
  - contains static salt-like string:
    - `Vmn34aAciYK00Hen26nT01`
