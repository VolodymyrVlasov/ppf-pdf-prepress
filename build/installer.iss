; installer.iss — Inno Setup script for PDF Pre-Press
; Run from build/ folder: ISCC.exe installer.iss
; Requires: PyInstaller build completed → ..\dist\pdf_prepress\

#define AppName      "PDF Pre-Press"
#define AppVersion   "1.0.0"
#define AppPublisher "Your Name"
#define AppExeName   "pdf_prepress.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist_installer
OutputBaseFilename=setup_pdf_prepress
SetupIconFile=..\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExeName}
DisableProgramGroupPage=no

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english";   MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Створити ярлик на робочому столі";    GroupDescription: "Додаткові значки:"; Flags: unchecked
Name: "startmenuicon"; Description: "Додати до меню Пуск";                 GroupDescription: "Додаткові значки:"; Flags: checkedonce
Name: "contextmenu";   Description: "Додати 'PDF Pre-Press' у контекстне меню PDF файлів"; GroupDescription: "Інтеграція:"; Flags: unchecked

[Files]
; Main application — entire PyInstaller one-dir output
Source: "..\dist\pdf_prepress\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start menu shortcut
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: startmenuicon
; Desktop shortcut
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Context menu entry for .pdf files — adds "PDF Pre-Press" to right-click menu
Root: HKCR; Subkey: ".pdf\shell\PDF Pre-Press";           ValueType: string; ValueName: ""; ValueData: "{#AppName}";                          Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: ".pdf\shell\PDF Pre-Press";           ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#AppExeName},0";             Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: ".pdf\shell\PDF Pre-Press\command";   ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1""";        Flags: uninsdeletekey; Tasks: contextmenu

[UninstallDelete]
; Remove settings file created at runtime
Type: files; Name: "{app}\settings.json"

[Run]
; Offer to launch the app after install
Filename: "{app}\{#AppExeName}"; Description: "Запустити {#AppName}"; Flags: nowait postinstall skipifsilent

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
      'Увага: Microsoft WebView2 Runtime не встановлено.' + #13#10 +
      'Програма може не запуститись.' + #13#10 + #13#10 +
      'Завантажте WebView2 Runtime з:' + #13#10 +
      'https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10 + #13#10 +
      'Встановіть WebView2 перед першим запуском PDF Pre-Press.',
      mbInformation, MB_OK);
end;
