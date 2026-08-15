@echo off
setlocal
cd /d "%~dp0"

if exist gradlew.bat (
  echo Building signed release AAB...
  call gradlew.bat bundleRelease
  if errorlevel 1 exit /b %errorlevel%
  echo.
  echo Building signed release APK for direct install...
  call gradlew.bat assembleRelease
  if errorlevel 1 exit /b %errorlevel%
  echo.
  echo Done.
  echo AAB output:
  echo app\build\outputs\bundle\release\app-release.aab
  echo APK output:
  echo app\build\outputs\apk\release\app-release.apk
  goto :eof
)

echo Gradle wrapper not found yet.
echo Open this folder in Android Studio once, let it sync, then run this script again or build from Android Studio.
pause
exit /b 1
