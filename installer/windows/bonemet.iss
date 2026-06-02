; Inno Setup script for BoneMet Workstation (Windows)
; Build steps:
;   1) make release-pack-windows
;   2) make windows-setup BONEMET_VERSION=<ver>
;      or: installer\windows\build_installer.ps1 -Version <ver>
;      or: scripts\build-windows-setup.ps1 -Version <ver>
;   (ISCC auto-detected; override with $env:BONEMET_ISCC)
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

#define AppIconName "bonemet.ico"

; 与 scripts/win_uninstall_common.py APP_UNINSTALL_KEY 一致
; Inno Setup 注册表子键名为 {GUID}_is1（含花括号）；zip 便携登记为 GUID（无花括号、无 _is1）
#define UninstallRegGuid "B4B0E18E-6E85-4E6E-9A2A-6C8F3A9D4E7B"
#define UninstallRegKeyInno "Software\Microsoft\Windows\CurrentVersion\Uninstall\{" + UninstallRegGuid + "}_is1"
#define UninstallRegKeyZip "Software\Microsoft\Windows\CurrentVersion\Uninstall\" + UninstallRegGuid

[Setup]
AppId={{B4B0E18E-6E85-4E6E-9A2A-6C8F3A9D4E7B}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
; 允许用户选择/修改安装目录（含升级时改路径；见 ShouldSkipPage）
DisableDirPage=no
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
; 安装到 Program Files 等需写权限目录时提示提升（仍可在对话框选「仅当前用户」）
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; 设置 → 应用 → 已安装的应用 中显示的名称与卸载入口
UninstallDisplayName={#MyAppDisplayName}
#ifexist "bonemet.ico"
SetupIconFile=bonemet.ico
UninstallDisplayIcon={app}\{#AppIconName}
#else
UninstallDisplayIcon={app}\{#MyAppExeName}
#endif
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=BoneMet-Workstation-{#AppVersion}-Setup
OutputDir=..\..\dist-release
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern

[Languages]
; Some Inno Setup installs may not include all language files. Fall back to Default.isl.
#ifexist "compiler:Languages\ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "keepdata"; Description: "保留用户数据 (data\ 下病例/队列/日志等，不含 models；models 由下一项单独控制)"; GroupDescription: "升级/重装选项:"; Flags: checkedonce; Check: IsUpgradeInstall
Name: "keepmodels"; Description: "保留 AI 模型 (data\models)"; GroupDescription: "升级/重装选项:"; Flags: unchecked; Check: IsUpgradeInstall
Name: "reinstalldeps"; Description: "重新安装 Python 依赖 (pip，需联网)"; GroupDescription: "升级/重装选项:"; Flags: unchecked; Check: IsUpgradeInstall
Name: "desktopicon"; Description: "创建桌面图标"; GroupDescription: "附加任务:"; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#ifexist "bonemet.ico"
Name: "{autoprograms}\{#MyAppDisplayName}\启动"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"
Name: "{autoprograms}\{#MyAppDisplayName}\停止"; Filename: "{app}\{#MyAppStopName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"
Name: "{autoprograms}\{#MyAppDisplayName}\重新安装"; Filename: "{app}\重新安装.bat"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"
Name: "{autoprograms}\{#MyAppDisplayName}\卸载"; Filename: "{uninstallexe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"
Name: "{autoprograms}\{#MyAppDisplayName}\日志目录"; Filename: "{app}\data\logs"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\{#AppIconName}"
#else
Name: "{autoprograms}\{#MyAppDisplayName}\启动"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\停止"; Filename: "{app}\{#MyAppStopName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\重新安装"; Filename: "{app}\重新安装.bat"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\卸载"; Filename: "{uninstallexe}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName}\日志目录"; Filename: "{app}\data\logs"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"; Check: ShouldRunPostInstallFullSetup
Filename: "{cmd}"; Parameters: "/c set BONEMET_SKIP_INSTALL=1&& ""{app}\{#MyAppExeName}"""; Description: "立即启动 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"; Check: ShouldRunPostInstallSkipPip

[UninstallRun]
Filename: "{app}\{#MyAppStopName}"; Flags: runhidden waituntilterminated; WorkingDir: "{app}"

[Code]
var
  BackupDir: string;
  PreviousInstallDir: string;

function TryQueryInstallLocation(const RootKey: Integer; const SubKey: string; var OutDir: string): Boolean;
var
  Uninst: string;
begin
  Result := False;
  OutDir := '';
  if RegQueryStringValue(RootKey, SubKey, 'InstallLocation', OutDir) and (OutDir <> '') then
  begin
    OutDir := RemoveBackslashUnlessRoot(OutDir);
    Result := True;
    Exit;
  end;
  { InstallLocation 缺失时从 UninstallString 解析（unins000.exe / 卸载.bat 所在目录） }
  if RegQueryStringValue(RootKey, SubKey, 'UninstallString', Uninst) and (Uninst <> '') then
  begin
    Uninst := RemoveQuotes(Uninst);
    OutDir := ExtractFileDir(Uninst);
    if OutDir <> '' then
    begin
      OutDir := RemoveBackslashUnlessRoot(OutDir);
      Result := True;
    end;
  end;
end;

{ 从卸载注册表读取已登记安装路径 Inno 子键为 花括号+GUID+_is1 或 zip 无花括号 }
function GetRegisteredInstallDir(): string;
var
  Loc: string;
begin
  Result := '';
  if TryQueryInstallLocation(HKLM64, '{#UninstallRegKeyInno}', Loc) then
    Result := Loc
  else if TryQueryInstallLocation(HKLM32, '{#UninstallRegKeyInno}', Loc) then
    Result := Loc
  else if TryQueryInstallLocation(HKCU64, '{#UninstallRegKeyInno}', Loc) then
    Result := Loc
  else if TryQueryInstallLocation(HKCU32, '{#UninstallRegKeyInno}', Loc) then
    Result := Loc
  else if TryQueryInstallLocation(HKCU64, '{#UninstallRegKeyZip}', Loc) then
    Result := Loc
  else if TryQueryInstallLocation(HKCU32, '{#UninstallRegKeyZip}', Loc) then
    Result := Loc;
end;

function InitializeSetup(): Boolean;
begin
  PreviousInstallDir := GetRegisteredInstallDir();
  Result := True;
end;

{ 系统内曾安装过本 AppId → 升级/重装（与目标文件夹是否为空无关） }
function IsUpgradeInstall: Boolean;
begin
  Result := PreviousInstallDir <> '';
end;

function IsFreshInstall: Boolean;
begin
  Result := not IsUpgradeInstall;
end;

{ 首次安装结束：允许启动脚本跑 pip（若无标记） }
function ShouldRunPostInstallFullSetup: Boolean;
begin
  Result := not IsUpgradeInstall;
end;

{ 升级结束：仅启动服务；pip 仅在勾选 reinstalldeps 时由 MaybeReinstallDeps 执行 }
function ShouldRunPostInstallSkipPip: Boolean;
begin
  Result := IsUpgradeInstall;
end;

function InstallSourceDir(): string;
begin
  if PreviousInstallDir <> '' then
    Result := PreviousInstallDir
  else
    Result := ExpandConstant('{app}');
end;

function NormalizeDirPath(const D: string): string;
begin
  if D = '' then
    Result := ''
  else
    Result := Lowercase(RemoveBackslashUnlessRoot(D));
end;

{ 用户选择的新路径与注册表中的旧路径不同 }
function IsRelocatedInstall: Boolean;
begin
  Result := IsUpgradeInstall and
    (NormalizeDirPath(PreviousInstallDir) <> NormalizeDirPath(ExpandConstant('{app}')));
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { 升级时也显示「目标文件夹」页，便于改路径（Inno 默认升级会跳过） }
  if PageID = wpSelectDir then
    Result := False
  else
    Result := False;
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

procedure StopInstallAt(const AppDir: string);
var
  ResultCode: Integer;
begin
  if FileExists(AppDir + '\{#MyAppStopName}') then
    Exec('cmd.exe', '/c call "' + AppDir + '\{#MyAppStopName}" silent',
      AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function TryQuietUninstallRegistry(const RootKey: Integer; const SubKey: string): Boolean;
var
  QuietCmd: string;
  ResultCode: Integer;
begin
  Result := False;
  if RegQueryStringValue(RootKey, SubKey, 'QuietUninstallString', QuietCmd) and (QuietCmd <> '') then
  begin
    Exec('cmd.exe', '/c ' + QuietCmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Result := True;
  end;
end;

{ 换路径升级：卸载并删除旧安装目录（备份已在临时目录） }
procedure RemoveOldInstallation;
var
  OldDir, Uninst: string;
  ResultCode: Integer;
begin
  if not IsRelocatedInstall then Exit;
  OldDir := PreviousInstallDir;
  StopInstallAt(OldDir);
  Uninst := OldDir + '\unins000.exe';
  if FileExists(Uninst) then
    Exec(Uninst, '/SILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
  else
  begin
    if not TryQuietUninstallRegistry(HKLM64, '{#UninstallRegKeyInno}') then
      if not TryQuietUninstallRegistry(HKLM32, '{#UninstallRegKeyInno}') then
        if not TryQuietUninstallRegistry(HKCU64, '{#UninstallRegKeyInno}') then
          TryQuietUninstallRegistry(HKCU64, '{#UninstallRegKeyZip}');
  end;
  if DirExists(OldDir) then
    DelTree(OldDir, True, True, True);
end;

procedure BackupUserData;
var
  AppDir: string;
begin
  BackupDir := '';
  if not IsUpgradeInstall then Exit;
  AppDir := InstallSourceDir();
  BackupDir := ExpandConstant('{tmp}\bonemet-backup-' + GetDateTimeString('yyyymmddhhnnss', #0, #0));
  ForceDirectories(BackupDir);
  if IsTaskSelected('keepdata') then
  begin
    ExecCopyTree(AppDir + '\data\cases', BackupDir + '\data\cases');
    ExecCopyTree(AppDir + '\data\export', BackupDir + '\data\export');
    ExecCopyTree(AppDir + '\data\incoming', BackupDir + '\data\incoming');
    ExecCopyTree(AppDir + '\data\queue', BackupDir + '\data\queue');
    ExecCopyTree(AppDir + '\data\logs', BackupDir + '\data\logs');
    ExecCopyFile(AppDir + '\config\local.yaml', BackupDir + '\config\local.yaml');
  end;
  if IsTaskSelected('keepmodels') then
    ExecCopyTree(AppDir + '\data\models', BackupDir + '\data\models');
  { 换路径且不重装 pip：旧目录将被删除，须把已安装的 python 与标记一并拷到临时目录 }
  if (not IsTaskSelected('reinstalldeps')) and IsRelocatedInstall then
  begin
    ExecCopyTree(AppDir + '\python', BackupDir + '\python');
    ExecCopyFile(AppDir + '\.bonemet_installed', BackupDir + '\.bonemet_installed');
  end;
end;

procedure CleanupNotKept;
var
  AppDir: string;
begin
  if not IsUpgradeInstall then Exit;
  AppDir := InstallSourceDir();
  if not IsTaskSelected('keepdata') then
  begin
    DelTree(AppDir + '\data', True, True, True);
    DeleteFile(AppDir + '\config\local.yaml');
  end
  else if not IsTaskSelected('keepmodels') then
    DelTree(AppDir + '\data\models', True, True, True);
end;

procedure PruneProgramFilesBeforeInstall;
var
  AppDir: string;
begin
  { 复制新包之前：清空旧程序目录（用户数据已在 CleanupNotKept 处理） }
  if not IsUpgradeInstall then Exit;
  AppDir := ExpandConstant('{app}');
  if DirExists(AppDir + '\apps') then
    DelTree(AppDir + '\apps', True, True, True);
  if DirExists(AppDir + '\packages') then
    DelTree(AppDir + '\packages', True, True, True);
  if DirExists(AppDir + '\scripts') then
    DelTree(AppDir + '\scripts', True, True, True);
  if DirExists(AppDir + '\deploy') then
    DelTree(AppDir + '\deploy', True, True, True);
  if DirExists(AppDir + '\docs') then
    DelTree(AppDir + '\docs', True, True, True);
  if DirExists(AppDir + '\schemas') then
    DelTree(AppDir + '\schemas', True, True, True);
  if DirExists(AppDir + '\bin') then
    DelTree(AppDir + '\bin', True, True, True);
  if IsTaskSelected('reinstalldeps') then
  begin
    if DirExists(AppDir + '\python') then
      DelTree(AppDir + '\python', True, True, True);
    DeleteFile(AppDir + '\.bonemet_installed');
  end;
  DeleteFile(AppDir + '\requirements.txt');
  DeleteFile(AppDir + '\Makefile');
  DeleteFile(AppDir + '\安装并启动.bat');
  DeleteFile(AppDir + '\停止BoneMet.bat');
  DeleteFile(AppDir + '\重新安装.bat');
  DeleteFile(AppDir + '\卸载.bat');
  DeleteFile(AppDir + '\修复模型配置.bat');
  DeleteFile(AppDir + '\bonemet.ico');
  DeleteFile(AppDir + '\bonemet.png');
  DeleteFile(AppDir + '\使用说明.txt');
  DeleteFile(AppDir + '\.bonemet_manifest.json');
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
    ExecCopyTree(BackupDir + '\data\logs', AppDir + '\data\logs');
    ExecCopyFile(BackupDir + '\config\local.yaml', AppDir + '\config\local.yaml');
  end;
  if IsTaskSelected('keepmodels') then
    ExecCopyTree(BackupDir + '\data\models', AppDir + '\data\models');
  if (not IsTaskSelected('reinstalldeps')) and IsRelocatedInstall then
  begin
    ExecCopyTree(BackupDir + '\python', AppDir + '\python');
    ExecCopyFile(BackupDir + '\.bonemet_installed', AppDir + '\.bonemet_installed');
  end;
end;

procedure RunPruneStaleFiles;
var
  AppDir, Cmd, Py: string;
  ResultCode: Integer;
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
  Exec('cmd.exe', '/c set BONEMET_FORCE_INSTALL=1&& call "' + AppDir + '\{#MyAppExeName}"', AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

{ 升级且未重装 pip：若依赖仍在但标记被误删，补写标记以免下次误触发 pip }
procedure EnsureInstallMarkerIfDepsKept;
var
  AppDir, MarkerPath: string;
begin
  if not IsUpgradeInstall then Exit;
  if IsTaskSelected('reinstalldeps') then Exit;
  AppDir := ExpandConstant('{app}');
  MarkerPath := AppDir + '\.bonemet_installed';
  if FileExists(MarkerPath) then Exit;
  if FileExists(AppDir + '\python\python.exe') and DirExists(AppDir + '\python\Lib\site-packages') then
    SaveStringToFile(MarkerPath, 'installed' + #13#10, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { 升级时序见 docs/PACKAGING.md「Setup 升级时序」 }
  if CurStep = ssInstall then
  begin
    if IsUpgradeInstall then
    begin
      BackupUserData;
      CleanupNotKept;
      if IsRelocatedInstall then
        RemoveOldInstallation;
      PruneProgramFilesBeforeInstall;
    end;
  end;
  if CurStep = ssPostInstall then
  begin
    { 须先 [Files] 才有新 .bonemet_manifest.json；先清单收尾再还原用户/pip，避免覆盖保留项 }
    RunPruneStaleFiles;
    RestoreUserData;
    EnsureInstallMarkerIfDepsKept;
    MaybeReinstallDeps;
    { 之后 [Run]：升级用 BONEMET_SKIP_INSTALL=1 仅启动；首次安装才允许脚本内 pip }
  end;
end;

