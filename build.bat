@echo off
REM ===========================================================================
REM  build.bat  -  builds ONE installer (LoreSetup.exe) you can send.
REM
REM  Your friends need nothing installed. YOU need (one time, on this PC):
REM    * Python (you have it)
REM    * Inno Setup  ->  https://jrsoftware.org/isdl.php   (free)
REM
REM  ONE-TIME PREP in this folder:
REM    Make  ffmpeg\bin  and put ffmpeg.exe AND ffprobe.exe inside it.
REM    (Run  where ffmpeg  to find your copies, or download from gyan.dev.)
REM
REM  Then just double-click this file. None of this touches your live install.
REM ===========================================================================
cd /d "%~dp0"

REM ---- find Python (it may not be on PATH in a plain CMD window) ----------
set "PYEXE="
where python >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE where py >nul 2>&1 && set "PYEXE=py -3"
if not defined PYEXE (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
  )
)
if not defined PYEXE (
  echo   *** Python was not found. Install it from python.org (tick "Add to
  echo       PATH" in its installer^), then run this file again.
  goto :err
)
echo Using Python: %PYEXE%

echo [1/4] Installing build tools + dependencies...
REM For a REPRODUCIBLE build, pin versions once on a known-good setup:
REM     pip freeze > requirements-lock.txt
if exist requirements-lock.txt (
  %PYEXE% -m pip install -r requirements-lock.txt || goto :err
) else (
  %PYEXE% -m pip install --upgrade pyinstaller psutil PyAudioWPatch pystray pillow pywebview || goto :err
)

echo.
echo [2/4] Bundling the app into an exe...
if not exist version.txt (
  echo   *** version.txt not found next to build.bat. It stamps the program name
  echo       "Lore" and publisher "Gate" into the exe. Put version.txt here.
  goto :err
)
if not exist ui.html (
  echo   *** ui.html not found next to build.bat. The tome IS the interface -
  echo       without it the app falls back to a console watcher.
  goto :err
)
REM known_games.txt is the baked windowed-game auto-detect list. The build
REM survives without it (the app just says so in its log), so only bundle it
REM when it's actually here - an unconditional --add-data would abort PyInstaller.
set "KGDATA="
if exist known_games.txt set KGDATA=--add-data "known_games.txt;."
if not exist known_games.txt echo   * known_games.txt not found - building without the baked game list.
%PYEXE% -m PyInstaller --noconfirm --clean ^
  --name Lore ^
  --onedir ^
  --windowed ^
  --icon lore.ico ^
  --version-file version.txt ^
  --add-data "ui.html;." ^
  %KGDATA% ^
  --collect-all pyaudiowpatch ^
  --collect-all pystray ^
  --collect-all webview ^
  --collect-all clr_loader ^
  --hidden-import clr ^
  --hidden-import pystray._win32 ^
  --hidden-import PIL.Image ^
  --hidden-import psutil ^
  lore.py || goto :err

set APP=dist\Lore

echo.
echo [3/4] Adding ffmpeg + support files...
if exist lore.ico ( copy /y lore.ico "%APP%\" >nul ) else (
  echo   *** WARNING: lore.ico not found - the app will build but use a
  echo       generic icon. Put lore.ico next to build.bat.
)
copy /y ui.html "%APP%\" >nul
if exist known_games.txt copy /y known_games.txt "%APP%\" >nul
REM ffmpeg is NOT optional - without both exes the installed app cannot record,
REM so refuse to produce a broken installer rather than merely warning.
if not exist ffmpeg\bin\ffmpeg.exe (
  echo   *** ffmpeg\bin\ffmpeg.exe is missing. Put ffmpeg.exe AND ffprobe.exe
  echo       in ffmpeg\bin next to build.bat, then run this again.
  goto :err
)
if not exist ffmpeg\bin\ffprobe.exe (
  echo   *** ffmpeg\bin\ffprobe.exe is missing ^(ffmpeg.exe alone is not
  echo       enough - thumbnails, durations and A/V sync need ffprobe^).
  goto :err
)
xcopy /e /i /y ffmpeg "%APP%\ffmpeg" >nul
if exist games.txt copy /y games.txt "%APP%\" >nul
if exist app_launchers xcopy /e /i /y app_launchers "%APP%\" >nul

echo.
echo [4/4] Compiling the installer...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  "%ISCC%" installer.iss || goto :err
  echo.
  echo ===========================================================================
  echo  DONE.  Send this ONE file to your friends:
  echo      installer_output\LoreSetup.exe
  echo  They double-click it, click through the wizard, and the tome is theirs.
  echo ===========================================================================
) else (
  echo Inno Setup not found.
  echo Install it from https://jrsoftware.org/isdl.php  then either re-run this
  echo file, or double-click installer.iss and press F9 to build the installer.
)
echo.
pause
exit /b 0

:err
echo.
echo Build failed - see the error above. Make sure Python is on PATH.
pause
exit /b 1
