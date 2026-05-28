; Inno Setup script for BoneMet Workstation (Windows)
; Build steps:
;   1) Create release pack folder: make release-pack-windows
;   2) Run Inno Setup: iscc bonemet.iss
;
; Notes:
; - This installer ships the app files + bundled models (if BUNDLE_MODELS=1).
; - Python dependencies are installed on first run by install-and-run.bat (online).
; - For code signing, see installer/windows/sign_installer.ps1

#define MyAppName "BoneMet Workstation"
#define MyAppPublisher "BoneMet"
#define MyAppURL "https://example.invalid"
#define MyAppExeName "安装并启动.bat"
#define MyAppStopName "停止BoneMet.bat"

; You can override these via ISCC /D options
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

#ifndef SourceDir
  ; Point to a prepared release-pack folder (dist-release/BoneMet-Workstation-<ver>-win-x64)
  #define SourceDir "..\\..\\dist-release\\BoneMet-Workstation-" + AppVersion + "-win-x64"
#endif

[Setup]
AppId={{B4B0E18E-6E85-4E6E-9A2A-6C8F3A9D4E7B}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=BoneMet-Workstation-{#AppVersion}-Setup
OutputDir=..\..\dist-release
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
; Some Inno Setup installs may not include all language files. Fall back to Default.isl.
#ifexist "C:\Program Files (x86)\Inno Setup 6\Languages\ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "创建桌面图标"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}\启动"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppName}\停止"; Filename: "{app}\{#MyAppStopName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppName}\日志目录"; Filename: "{app}\data\logs"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

