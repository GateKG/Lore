@echo off
REM Runs the whole deterministic roster; stops listing at the end with
REM a summary. Each suite prints "N ok, M failed" and exits nonzero on
REM failure.
setlocal enabledelayedexpansion
set PYTHONUTF8=1
cd /d "%~dp0"

REM ---- preflight: fail ONCE with a precise message, never mid-suite.
REM The roster imports lore.py, whose only hard module-level need is
REM psutil; micheal additionally drives _mic_watch, whose first line
REM imports pyaudiowpatch on a daemon thread - without preflight that
REM surfaces as a cryptic thread traceback 12 seconds into the suite.
python -c "import psutil, pyaudiowpatch" >nul 2>&1
if errorlevel 1 (
  echo PREFLIGHT FAILED: this python cannot import psutil and/or
  echo PyAudioWPatch. Fix with:  pip install psutil PyAudioWPatch
  exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
  echo PREFLIGHT FAILED: node is required for paneltest and checkui.
  exit /b 1
)
if not exist "C:\Program Files\Lore\ffmpeg\bin\ffmpeg.exe" (
  echo NOTE: audiotest and midchange lean on the installed LORE ffmpeg
  echo at "C:\Program Files\Lore\ffmpeg\bin" - expect them to fail on
  echo a machine without the app installed.
)

set FAILED=
for %%t in (codex327test codex326test codex325test codex324test codex323test asr322test
            afkai320test afkrace320test fresh319test fleet319test
            afk2test afktest pairtest freezetest schedtest sched4test
            aud302test aud303test silvertest gatetest295 micheal
            mictest audiotest midchange fetchtest
            hud330test echo330test title330test owing330test black332test outcome332test
            tracks331test src331settingstest src331dumptest
            src331taptest src331watchtest src331runtest src331walktest
            src331test sources331_describer sources331_panel
            sources331_shelf hl331test hype331test hlsplit331test
            sns331test) do (
  echo ===== %%t =====
  python "%%t.py"
  if errorlevel 1 set FAILED=!FAILED! %%t
)
echo ===== rectests =====
python "rectests\recorder_scenarios.py"
if errorlevel 1 set FAILED=!FAILED! recorder_scenarios
echo ===== cliptest =====
node "cliptest.js"
if errorlevel 1 set FAILED=!FAILED! cliptest
echo ===== paneltest =====
node "paneltest.js"
if errorlevel 1 set FAILED=!FAILED! paneltest
echo ===== checkui =====
node "checkui.js" "..\ui.html"
if errorlevel 1 set FAILED=!FAILED! checkui
echo.
if "!FAILED!"=="" (
  echo ALL SUITES GREEN
) else (
  echo FAILED:!FAILED!
  exit /b 1
)
