@echo off
setlocal
cd /d "%~dp0"

if exist gradlew.bat (
  call gradlew.bat assembleDebug
  goto :eof
)

echo Gradle wrapper not found yet.
echo Open this folder in Android Studio once, let it sync, then run this script again or build from Android Studio.
exit /b 1
