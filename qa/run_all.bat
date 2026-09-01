@echo off
REM Runs the whole deterministic roster; stops listing at the end with
REM a summary. Each suite prints "N ok, M failed" and exits nonzero on
REM failure.
setlocal enabledelayedexpansion
set PYTHONUTF8=1
cd /d "%~dp0"
set FAILED=
for %%t in (codex324test codex323test asr322test afkai320test
            afkrace320test fresh319test fleet319test afk2test afktest
            pairtest freezetest schedtest sched4test aud302test
            aud303test silvertest gatetest295 micheal mictest audiotest
            midchange fetchtest) do (
  echo ===== %%t =====
  python "%%t.py"
  if errorlevel 1 set FAILED=!FAILED! %%t
)
echo ===== rectests =====
python "rectests\recorder_scenarios.py"
if errorlevel 1 set FAILED=!FAILED! recorder_scenarios
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
