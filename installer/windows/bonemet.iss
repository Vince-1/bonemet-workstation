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
#define MyAppDisplayName "BoneMet 骨转移工作站"
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
; 设置 → 应用 → 已安装的应用 中显示的名称与卸载入口
UninstallDisplayName={#MyAppDisplayName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=BoneMet-Workstation-{#AppVersion}-Setup
OutputDir=..\..\dist-release
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
; Some Inno Setup installs may not include all language files. Fall back to Default.isl.
#ifexist "compiler:Languages\ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "keepdata"; Description: "保留病例与配置数据 (data\cases、config\local.yaml 等)"; GroupDescription: "升级/重装选项:"; Flags: checkedonce
Name: "keepmodels"; Description: "保留 AI 模型 (data\models)"; GroupDescription: "升级/重装选项:"; Flags: unchecked
Name: "reinstalldeps"; Description: "重新安装 Python 依赖 (pip，需联网)"; GroupDescription: "升级/重装选项:"; Flags: unchecked
Name: "desktopicon"; Description: "创建桌面图标"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppDisplayName}\启动"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\停止"; Filename: "{app}\{#MyAppStopName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\重新安装"; Filename: "{app}\重新安装.bat"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\卸载"; Filename: "{uninstallexe}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\日志目录"; Filename: "{app}\data\logs"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"; Check: not IsUpgradeInstall
Filename: "{cmd}"; Parameters: "/c set BONEMET_SKIP_INSTALL=1&& ""{app}\{#MyAppExeName}"""; Description: "立即启动 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"; Check: IsUpgradeInstall

[UninstallRun]
Filename: "{app}\{#MyAppStopName}"; Flags: runhidden waituntilterminated; WorkingDir: "{app}"

[Code]
var
  BackupDir: string;

function IsUpgradeInstall: Boolean;
begin
  Result := DirExists(ExpandConstant('{app}')) and
    FileExists(ExpandConstant('{app}\{#MyAppExeName}'));
end;

procedure ExecCopyTree(const Src, Dst: string);
var
  ResultCode: Integer;
begin
  if not DirExists(Src) then Exit;
  ForceDirectories(Dst);
  Exec('cmd.exe', '/c xcopy "' + Src + '" "' + Dst + '" /E /I /Y /Q', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure ExecCopyFile(const Src, Dst: string);
var
  ResultCode: Integer;
begin
  if not FileExists(Src) then Exit;
  ForceDirectories(ExtractFileDir(Dst));
  Exec('cmd.exe', '/c copy /Y "' + Src + '" "' + Dst + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure BackupUserData;
var
  AppDir: string;
begin
  BackupDir := '';
  if not IsUpgradeInstall then Exit;
  AppDir := ExpandConstant('{app}');
  BackupDir := ExpandConstant('{tmp}\bonemet-backup-' + GetDateTimeString('yyyymmddhhnnss', #0, #0));
  ForceDirectories(BackupDir);
  if IsTaskSelected('keepdata') then
  begin
    ExecCopyTree(AppDir + '\data\cases', BackupDir + '\data\cases');
    ExecCopyTree(AppDir + '\data\export', BackupDir + '\data\export');
    ExecCopyTree(AppDir + '\data\incoming', BackupDir + '\data\incoming');
    ExecCopyTree(AppDir + '\data\queue', BackupDir + '\data\queue');
    ExecCopyFile(AppDir + '\config\local.yaml', BackupDir + '\config\local.yaml');
  end;
  if IsTaskSelected('keepmodels') then
    ExecCopyTree(AppDir + '\data\models', BackupDir + '\data\models');
end;

procedure CleanupNotKept;
var
  AppDir: string;
begin
  if not IsUpgradeInstall then Exit;
  AppDir := ExpandConstant('{app}');
  if not IsTaskSelected('keepdata') then
  begin
    DelTree(AppDir + '\data\cases', True, True, True);
    DelTree(AppDir + '\data\export', True, True, True);
    DelTree(AppDir + '\data\incoming', True, True, True);
    DelTree(AppDir + '\data\queue', True, True, True);
    DeleteFile(AppDir + '\config\local.yaml');
  end;
  if not IsTaskSelected('keepmodels') then
    DelTree(AppDir + '\data\models', True, True, True);
end;

procedure RestoreUserData;
var
  AppDir: string;
begin
  if BackupDir = '' then Exit;
  if not DirExists(BackupDir) then Exit;
  AppDir := ExpandConstant('{app}');
  if IsTaskSelected('keepdata') then
  begin
    ExecCopyTree(BackupDir + '\data\cases', AppDir + '\data\cases');
    ExecCopyTree(BackupDir + '\data\export', AppDir + '\data\export');
    ExecCopyTree(BackupDir + '\data\incoming', AppDir + '\data\incoming');
    ExecCopyTree(BackupDir + '\data\queue', AppDir + '\data\queue');
    ExecCopyFile(BackupDir + '\config\local.yaml', AppDir + '\config\local.yaml');
  end;
  if IsTaskSelected('keepmodels') then
    ExecCopyTree(BackupDir + '\data\models', AppDir + '\data\models');
end;

procedure RunPruneStaleFiles;
var
  AppDir, Cmd, Py, ResultCode: Integer;
  KeepData, KeepModels, ReinstallDeps: string;
begin
  if not IsUpgradeInstall then Exit;
  AppDir := ExpandConstant('{app}');
  if not FileExists(AppDir + '\scripts\release_manifest.py') then Exit;
  Py := AppDir + '\python\python.exe';
  if not FileExists(Py) then Py := 'python';
  KeepData := '0';
  if IsTaskSelected('keepdata') then KeepData := '1';
  KeepModels := '0';
  if IsTaskSelected('keepmodels') then KeepModels := '1';
  ReinstallDeps := '0';
  if IsTaskSelected('reinstalldeps') then ReinstallDeps := '1';
  Cmd := '/c set BONEMET_KEEP_DATA=' + KeepData +
    '&& set BONEMET_KEEP_MODELS=' + KeepModels +
    '&& set BONEMET_REINSTALL_DEPS=' + ReinstallDeps +
    '&& "' + Py + '" "' + AppDir + '\scripts\release_manifest.py" prune';
  Exec('cmd.exe', Cmd, AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure MaybeReinstallDeps;
var
  AppDir: string;
  ResultCode: Integer;
begin
  if not IsUpgradeInstall then Exit;
  if not IsTaskSelected('reinstalldeps') then Exit;
  AppDir := ExpandConstant('{app}');
  DeleteFile(AppDir + '\.bonemet_installed');
  Exec('cmd.exe', '/c set BONEMET_FORCE_INSTALL=1&& call "' + AppDir + '\scripts\install-and-run.bat"', AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    BackupUserData;
  if CurStep = ssPostInstall then
  begin
    CleanupNotKept;
    RestoreUserData;
    RunPruneStaleFiles;
    MaybeReinstallDeps;
  end;
end;

