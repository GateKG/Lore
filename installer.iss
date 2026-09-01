; ===========================================================================
;  installer.iss  -  builds ONE LoreSetup.exe
;
;  This packs the bundled app (from dist\Lore) into a single setup wizard.
;  A friend runs that one file, clicks through, and ends up with a working
;  recorder wrapped in a tome - no Python, no ffmpeg, no batch files.
;
;  Build it: install Inno Setup (https://jrsoftware.org/isdl.php) once, then
;  either run build.bat (it compiles this automatically) or double-click this
;  file and press F9.
; ===========================================================================

[Setup]
AppId={{7C1A44D9-63BF-4A0E-9E7D-2F4B8C5A930E}
AppName=Lore
AppVersion=3.24
VersionInfoVersion=3.24.0
; A 64-bit app should live in the real Program Files (v1 landed in x86;
; upgrades reuse whichever folder is already installed, so nothing breaks).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppPublisher=Gate
AppCopyright=Created by Gate
; Same name the app holds while running, so reinstalling/updating can detect a
; running copy and offer to close it instead of failing on a locked file.
AppMutex=Lore_SingleInstance_Gate
DefaultDirName={autopf}\Lore
DefaultGroupName=Lore
DisableProgramGroupPage=yes
PrivilegesRequired=admin
; (updates reuse the folder the user originally chose - the Inno default)
OutputDir=installer_output
OutputBaseFilename=LoreSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=lore.ico
UninstallDisplayName=Lore
UninstallDisplayIcon={app}\Lore.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startupicon"; Description: "Start automatically (hidden) when I log in"; GroupDescription: "Startup:"
Name: "desktopicon";  Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
; The entire built app folder (exe + runtime + bundled ffmpeg + the tome).
Source: "dist\Lore\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Lore";           Filename: "{app}\Lore.exe"; IconFilename: "{app}\lore.ico"; Comment: "The living tome - watches for games and records them"
Name: "{group}\Uninstall Lore"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Lore";     Filename: "{app}\Lore.exe"; IconFilename: "{app}\lore.ico"; Tasks: desktopicon
; Hidden autostart at login (only if the user ticked the task).
Name: "{userstartup}\Lore";     Filename: "{app}\Lore.exe"; Parameters: "--hidden"; Tasks: startupicon

[Run]
; Offered on the final wizard page: open the tome.
Filename: "{app}\Lore.exe"; Description: "Open LORE now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Stop the background recorder before removing files (otherwise the exe is locked).
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM Lore.exe"; Flags: runhidden; RunOnceId: "StopRecorder"
; A transcription job may still hold whisper files open after Lore.exe dies.
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM whisper-cli.exe"; Flags: runhidden; RunOnceId: "StopWhisper"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files;          Name: "{userstartup}\Lore.lnk"
Type: filesandordirs; Name: "{localappdata}\Temp\lore_sfx"
; LORE keeps its settings, log and games list here - clean those up, but
; NEVER the models or the runtime: they are up to 32 GB the user chose to
; download, they are not ours to throw away on an uninstall, and a
; reinstall finds them again exactly where they were.
Type: files;          Name: "{localappdata}\Lore\*.json"
Type: files;          Name: "{localappdata}\Lore\*.txt"
Type: files;          Name: "{localappdata}\Lore\*.log*"
Type: files;          Name: "{localappdata}\Lore\*.key"
Type: files;          Name: "{localappdata}\Lore\*.lock"
Type: files;          Name: "{localappdata}\Lore\*.flag"
Type: files;          Name: "{localappdata}\Lore\*.gen"
Type: files;          Name: "{localappdata}\Lore\*.beat"
Type: files;          Name: "{localappdata}\Lore\*.reader"

[Code]
{ No default settings.json is written here on purpose. The app applies its own
  DEFAULTS on first run - and if Records (LORE's previous incarnation) is on
  this PC, LORE quietly inherits its settings, games list and file ownership
  on first launch. ONE source of truth lives in lore.py. }
procedure CurStepChanged(CurStep: TSetupStep);
var rc: Integer;
begin
  if CurStep = ssInstall then
    { Close any running copy BEFORE copying files, so nothing is locked and
      the install can't end up half-updated. }
    Exec(ExpandConstant('{cmd}'),
         '/C taskkill /F /IM Lore.exe',
         '', SW_HIDE, ewWaitUntilTerminated, rc);
  if CurStep = ssInstall then
    { An orphaned transcription child would keep whisper\ files locked. }
    Exec(ExpandConstant('{cmd}'),
         '/C taskkill /F /IM whisper-cli.exe',
         '', SW_HIDE, ewWaitUntilTerminated, rc);
end;
