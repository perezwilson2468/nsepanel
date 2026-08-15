# Ninja Sage Android

This folder is a separate Android Studio project which leaves your current desktop/web project untouched.

## What it does

- Reuses the existing Python automation logic from `core/` through Chaquopy.
- Wraps it in a native Android UI built with Jetpack Compose.
- Stores quick-login data locally on the device instead of using the remote quick-login hosting endpoint.
- Keeps `event_finisher.py` out of the Android action list because it depends on `tkinter` desktop UI and you said you don't really use it.

## Included actions

- Leveling
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

## Build notes

1. Open `android_app` in Android Studio.
2. Let Gradle sync and download the Android and Python dependencies.
3. Build an APK from Android Studio.
4. See `BUILD-APK.md` for the prepared release-signing setup and build scripts.

## Important notes

- The project uses Chaquopy, so Android Studio/Gradle will download Python packages during the first sync.
- Quick login is saved locally using Android encrypted storage.
- The Python core was copied into this Android project so your original files stay unchanged.
- A release keystore and `keystore.properties` have already been created for this project.
