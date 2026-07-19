; Inno Setup script for Voice Chat Soundboard.
; Compiles the already-built portable exe (dist\VoiceChatSoundboard.exe)
; into a proper Windows installer with Start Menu / desktop shortcuts and
; an uninstaller. Also checks whether VB-Audio CABLE looks installed and,
; if not, offers to open the download page.
;
; Build locally:   ISCC.exe installer.iss
; Build in CI:      ISCC.exe /DMyAppVersion=1.1.0 installer.iss
; (see .github/workflows/build.yml - it passes the version automatically)

#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

#define MyAppName "Voice Chat Soundboard"
#define MyAppPublisher "GoboVR"
#define MyAppURL "https://github.com/GoboVR/Soundboard"
#define MyAppExeName "VoiceChatSoundboard.exe"

[Setup]
; Fixed AppId so upgrades/uninstalls recognize previous installs correctly.
; Don't change this between releases.
AppId={{4C6C6F70-9B2E-4E7A-9C5A-2F1B8A7C5D3E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=VoiceChatSoundboard-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\VoiceChatSoundboard.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function VBCableInstalled(): Boolean;
begin
  { VB-Audio CABLE has installed into C:\Program Files\VB\CABLE\ across
    every version we've seen, regardless of Windows bitness, so checking
    both possible Program Files roots covers it. This is a best-effort
    check (not a hard requirement) - the app can still be installed and
    used without VB-CABLE if someone wants to wire up audio differently. }
  Result := DirExists(ExpandConstant('{pf}\VB\CABLE'))
    or DirExists(ExpandConstant('{pf32}\VB\CABLE'));
end;

procedure InitializeWizard();
var
  ErrorCode: Integer;
begin
  if not VBCableInstalled() then
  begin
    if MsgBox(
      'Voice Chat Soundboard needs VB-Audio CABLE (a free virtual audio driver) to route sound effects into your mic / voice chat.' + #13#10 + #13#10 +
      'It doesn''t look like VB-CABLE is installed on this PC yet.' + #13#10 + #13#10 +
      'Open the download page now? (You can install it before or after this setup finishes.)',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://vb-audio.com/Cable/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
  end;
end;
