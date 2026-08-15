# Ninja Sage Panel — Open Source

[![Trakteer](https://img.shields.io/badge/Support%20on-Trakteer-red?style=for-the-badge)](https://trakteer.id/theforgotten/tip)
[![PayPal](https://img.shields.io/badge/Donate-PayPal-blue?style=for-the-badge&logo=paypal)](https://paypal.me/Randomideax)

A cross-platform automation panel for Ninja Saga & Sage games.
Available as a **Desktop App** (Windows) and an **Android App**.
Serve as it is

---

## Project Structure

```

desktop_app/       # Python desktop app (FastAPI + pywebview)
├── main.py
├── multi-launcher.py
├── requirements.txt
├── core/
├── data/
├── static/
└── templates/
android_app/       # Android app (Kotlin + Chaquopy Python)
├── app/
├── build.gradle.kts
├── gradlew / gradlew.bat
└── ...
```

---

## Desktop App

### Requirements

- Python **3.10** or higher (3.11 recommended)
- pip

### Installation

```bash
cd desktop_app
pip install -r requirements.txt
```

> **Windows users:** If `pywebview` fails to install, make sure you have the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) installed.

### How to Run

#### Single instance — browser mode

```bash
python main.py
```

Open your browser at: `http://127.0.0.1:8000`

#### Multi-instance launcher with native window (recommended)

```bash
python multi-launcher.py
```

Opens a native desktop window using `pywebview`. You can run multiple panel instances at once, each on its own port.

### Features

- Leveling
- Auto Exam
- Daily Missions
- Eudemon Boss
- Monster Hunt
- CD Event
- Anniversary Event
- Anniversary Special Mission
- Phantom Kyunoki
- Shadow War
- Pumpkin Event
- Yin Yang Event
- Christmas Event
- Thanksgiving Event

---

## Android App

### Requirements

- **Android Studio** (latest stable — Hedgehog or newer)
- Android SDK (API 24+)
- Internet connection for Gradle sync (downloads Python packages via Chaquopy)

### Installation and Build

1. Open the `android_app` folder in **Android Studio** (open `android_app` directly, not the root folder).
2. Wait for **Gradle sync** to complete — it will automatically download Python packages via Chaquopy (may take a few minutes on first run).
3. Connect your Android device or start an emulator.

#### Build Debug APK (for testing)

- In Android Studio: **Build → Build APK(s)**
- Output: `app/build/outputs/apk/debug/`

#### Build Release APK (for manual install)

- In Android Studio: **Build → Generate Signed Bundle / APK → APK**
- A release keystore is already included at: `keystore/ninjasage-release.jks`
- Output: `app/build/outputs/apk/release/`


#### Command Line (after Android Studio has synced at least once)

```bat
:: Build debug APK
build-debug.bat

:: Build release APK and AAB
build-release.bat

:: Build release AAB only (for Play Store)
build-play-aab.bat
```

Or using the Gradle wrapper directly:

```powershell
.\gradlew.bat assembleDebug
.\gradlew.bat assembleRelease
.\gradlew.bat bundleRelease
```

### How to Install APK on Android

1. Enable **Unknown Sources** on your device:
   - Settings → Security → Install unknown apps → allow your file manager or browser
2. Transfer the APK from `app/build/outputs/apk/debug/` or `apk/release/` to your device.
3. Tap the APK file on your device to install.

### Included Actions (Android)

- Leveling
- Auto Exam
- Daily Missions
- Eudemon Boss
- Monster Hunt
- CD Event
- Anniversary Event
- Anniversary Special Mission
- Phantom Kyunoki
- Shadow War
- Pumpkin Event
- Yin Yang Event
- Christmas Event
- Thanksgiving Event

### Important Notes

- Quick login data is stored **locally on the device** using Android encrypted storage.
- The Python automation core runs on-device via [Chaquopy](https://chaquo.com/chaquopy/) — no external server required.
- Keep `keystore/ninjasage-release.jks` and `keystore.properties` **private**. Losing the keystore means you cannot update the app with the same signing identity.

---

## Tech Stack

| Layer | Desktop | Android |
|---|---|---|
| Language | Python 3 | Kotlin + Python (Chaquopy) |
| UI | pywebview (native window) + HTML/CSS/JS | Jetpack Compose |
| Backend | FastAPI + uvicorn | Embedded Python core |
| Real-time | WebSockets | Coroutines |

---

## License

This project is under AGPLv3 licence.