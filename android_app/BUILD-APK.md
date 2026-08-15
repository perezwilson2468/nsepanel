# Build Android Release

## Ready-made signing

This project already includes:

- release keystore: `keystore/ninjasage-release.jks`
- signing config file: `keystore.properties`

The app build is already wired to use them automatically for release builds.

## Fastest way

1. Open this folder in Android Studio.
2. Let Android Studio install SDK/components and finish Gradle sync.
3. Build debug APK:
   - `Build` -> `Build APK(s)`
4. Build release AAB for Google Play Console:
   - `Build` -> `Generate Signed Bundle / APK`
   - choose `Android App Bundle`
   - choose module `app`
   - use the existing signing config if Android Studio asks, or build release directly
5. If you also want a release APK for manual install:
   - `Build` -> `Generate Signed Bundle / APK`
   - choose `APK`

## Command line

After Android Studio creates or downloads the Gradle wrapper, you can use:

```bat
build-debug.bat
build-release.bat
build-play-aab.bat
```

Or:

```powershell
.\gradlew.bat assembleDebug
.\gradlew.bat bundleRelease
.\gradlew.bat assembleRelease
```

## Output

- debug APK: `app/build/outputs/apk/debug/`
- release AAB: `app/build/outputs/bundle/release/`
- release APK: `app/build/outputs/apk/release/`

## Script Summary

- `build-debug.bat`: builds debug APK
- `build-play-aab.bat`: builds release AAB only
- `build-release.bat`: builds both release AAB and release APK

## Important

- Keep `keystore.properties` and `keystore/ninjasage-release.jks` private.
- If you lose this keystore, you will not be able to update the app with the same signing identity later.
