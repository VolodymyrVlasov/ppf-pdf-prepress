; installer.iss — Inno Setup script for PDF Pre-Press
; Run from build/ folder: ISCC.exe installer.iss
; Requires: PyInstaller build completed → ..\dist\pdf_prepress\

#define AppName      "PDF Pre-Press"
#define AppVersion   "1.0.0"
#define AppPublisher "PDF Pre-Press"
#define AppExeName   "pdf_prepress.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist_installer
OutputBaseFilename=setup_pdf_prepress
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Create a desktop shortcut";                        GroupDescription: "Additional icons:";    Flags: checkedonce
Name: "startmenuicon"; Description: "Add to Start Menu";                                GroupDescription: "Additional icons:";    Flags: checkedonce
Name: "contextmenu";   Description: "Add 'PDF Pre-Press' to right-click menu for PDF files"; GroupDescription: "Windows integration:"; Flags: unchecked

[Files]
; Main executable
Source: "..\dist\pdf_prepress\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; All dependencies from _internal folder
Source: "..\dist\pdf_prepress\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
; Desktop shortcut
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Context menu entry for .pdf files — adds "PDF Pre-Press" to right-click menu
Root: HKCR; Subkey: ".pdf\shell\PDF Pre-Press";         ValueType: string; ValueName: ""; ValueData: "{#AppName}";                   Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: ".pdf\shell\PDF Pre-Press\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: contextmenu

[UninstallDelete]
; Remove settings file created at runtime
Type: files; Name: "{app}\settings.json"

[Run]
; Offer to launch the app after install
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Check for Microsoft WebView2 Runtime (required by pywebview EdgeChromium backend)
function IsWebView2Installed(): Boolean;
var
  version: String;
begin
  Result :=
    RegQueryStringValue(
      HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', version) and (version <> '') and (version <> '0.0.0.0');
end;

procedure InitializeWizard();
begin
  if not IsWebView2Installed() then
    MsgBox(
      'Warning: Microsoft WebView2 Runtime is not installed.' + #13#10 +
      'The application may not start correctly.' + #13#10 + #13#10 +
      'Download from: https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10 +
      'Install it before launching PDF Pre-Press.',
      mbInformation, MB_OK);
end;
