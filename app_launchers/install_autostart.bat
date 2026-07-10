@echo off
cd /d "%~dp0"
echo Creating a startup entry so LORE wakes (in the tray) when you log in...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\Lore.lnk');" ^
  "$lnk.TargetPath = '%~dp0Lore.exe';" ^
  "$lnk.Arguments = '--hidden';" ^
  "$lnk.WorkingDirectory = '%~dp0';" ^
  "$lnk.Save()"
echo.
echo Done. LORE will start automatically (in the tray) at every login.
echo To undo: press Win+R, type  shell:startup  and delete "Lore".
pause
