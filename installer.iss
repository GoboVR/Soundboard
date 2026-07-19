; Inno Setup script for Gobo's Soundboard.
; Compiles the already-built portable exe (dist\GobosSoundboard.exe)
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

#define MyAppName "Gobo's Soundboard"
#define MyAppPublisher "GoboVR"
#define MyAppURL "https://github.com/GoboVR/Soundboard"
#define MyAppExeName "GobosSoundboard.exe"
; Same as MyAppName but with the apostrophe doubled - Pascal string literals
; in [Code] need '' to represent a literal ' inside a '...' string, but the
; preprocessor just pastes MyAppName's raw text in, so using MyAppName
; directly inside a Pascal string breaks the moment the name has a quote
; in it. Use this one instead of MyAppName anywhere inside [Code].
#define MyAppNamePascal "Gobo''s Soundboard"

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
OutputBaseFilename=GobosSoundboard-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\GobosSoundboard.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[InstallDelete]
; Cleans up leftovers from the pre-rename "Voice Chat Soundboard" builds
; (same AppId, so this counts as an upgrade and reuses the old install
; folder - but the old exe/shortcut names aren't in [Files]/[Icons]
; anymore, so without this they'd be orphaned instead of replaced).
Type: files; Name: "{app}\VoiceChatSoundboard.exe"
Type: files; Name: "{commonprograms}\Voice Chat Soundboard\Voice Chat Soundboard.lnk"
Type: files; Name: "{commonprograms}\Voice Chat Soundboard\Uninstall Voice Chat Soundboard.lnk"
Type: dirifempty; Name: "{commonprograms}\Voice Chat Soundboard"
Type: files; Name: "{autodesktop}\Voice Chat Soundboard.lnk"

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
      '{#MyAppNamePascal} needs VB-Audio CABLE (a free virtual audio driver) to route sound effects into your mic / voice chat.' + #13#10 + #13#10 +
      'It doesn''t look like VB-CABLE is installed on this PC yet.' + #13#10 + #13#10 +
      'Open the download page now? (You can install it before or after this setup finishes.)',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://vb-audio.com/Cable/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
  end;
end;
