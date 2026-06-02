# Shared Inno Setup helpers (dot-source from installer/windows/*.ps1)
# ISCC discovery order: -IsccPath / $env:BONEMET_ISCC / $env:INNO_SETUP_ISCC / PATH / default install dirs

function Get-BonemetRepoRoot {
  param([string]$ScriptRoot = $PSScriptRoot)
  return (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
}

function Find-InnoIscc {
  param([string]$Candidate = "")

  $try = @()
  if ($Candidate) { $try += $Candidate }
  if ($env:BONEMET_ISCC) { $try += $env:BONEMET_ISCC }
  if ($env:INNO_SETUP_ISCC) { $try += $env:INNO_SETUP_ISCC }

  foreach ($p in $try) {
    if ($p -and (Test-Path -LiteralPath $p)) {
      return (Resolve-Path -LiteralPath $p).Path
    }
    if ($p -match '^(iscc|ISCC)(\.exe)?$') {
      $cmd = Get-Command $p -ErrorAction SilentlyContinue
      if ($cmd) { return $cmd.Source }
    }
  }

  foreach ($name in @("ISCC.exe", "iscc.exe")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }

  $common = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 5\ISCC.exe"
  )
  foreach ($p in $common) {
    if ($p -and (Test-Path -LiteralPath $p)) { return $p }
  }
  return $null
}

function Get-BonemetReleasePackDir {
  param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$RepoRoot = ""
  )
  if (-not $RepoRoot) { $RepoRoot = Get-BonemetRepoRoot }
  Join-Path $RepoRoot "dist-release\BoneMet-Workstation-$Version-win-x64"
}

function Get-BonemetSetupExePath {
  param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$RepoRoot = ""
  )
  if (-not $RepoRoot) { $RepoRoot = Get-BonemetRepoRoot }
  Join-Path $RepoRoot "dist-release\BoneMet-Workstation-$Version-Setup.exe"
}

function Write-NativeProcessLines {
  param(
    [string]$Text,
    [System.ConsoleColor]$Color = [System.ConsoleColor]::Gray
  )
  if (-not $Text) { return }
  foreach ($line in ($Text -split "`r`n|`n|\r")) {
    if ($line.Length -gt 0) {
      Write-Host $line -ForegroundColor $Color
    }
  }
}

function Test-InteractiveConsole {
  try {
    return -not [Console]::IsOutputRedirected
  } catch {
    return $true
  }
}

function Invoke-LoggedNative {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string[]]$ArgumentList
  )

  # 交互式终端：继承控制台，ISCC 逐行输出（不重定向，避免管道缓冲导致结束时一口气打印）
  if (Test-InteractiveConsole) {
    $p = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) {
      throw "Command failed: $FilePath (exit $($p.ExitCode))"
    }
    return
  }

  # CI / 重定向输出：异步按行转发
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

  $escaped = foreach ($arg in $ArgumentList) {
    if ($arg -match '\s') {
      '"' + ($arg -replace '"', '""') + '"'
    } else {
      $arg
    }
  }
  $psi.Arguments = $escaped -join ' '

  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi

  $outEvent = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
    if ($EventArgs.Data) { Write-Host $EventArgs.Data }
  }
  $errEvent = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
    if ($EventArgs.Data) { Write-Host $EventArgs.Data -ForegroundColor Yellow }
  }

  try {
    [void]$proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    $proc.WaitForExit()
  } finally {
    Unregister-Event -SourceIdentifier $outEvent.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $errEvent.Name -ErrorAction SilentlyContinue
  }

  if ($proc.ExitCode -ne 0) {
    throw "Command failed: $FilePath (exit $($proc.ExitCode))"
  }
}

function Get-BonemetBundleModelsFlag {
  param([switch]$NoModels)
  if ($NoModels) { return "0" }
  if ($env:BUNDLE_MODELS -ne "") { return $env:BUNDLE_MODELS }
  return "1"
}

function Invoke-BonemetReleasePackWindows {
  param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$BashPath = "bash.exe",
    [string]$BundleModels = "1"
  )
  $root = Get-BonemetRepoRoot
  Push-Location $root
  try {
    Write-Host "==> Building release pack (BUNDLE_MODELS=$BundleModels)..." -ForegroundColor Cyan
    & $BashPath "-lc" "BONEMET_VERSION=$Version BONEMET_TARGET=windows BUNDLE_MODELS=$BundleModels bash scripts/build-release-pack.sh"
  } finally {
    Pop-Location
  }
}

function Invoke-BonemetSetupBuild {
  param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$IsccPath = "",
    [string]$SourceDir = "",
    [string]$IssPath = ""
  )

  $root = Get-BonemetRepoRoot
  if (-not $IssPath) {
    $IssPath = Join-Path $root "installer\windows\bonemet.iss"
  }
  if (-not $SourceDir) {
    $SourceDir = Get-BonemetReleasePackDir -Version $Version -RepoRoot $root
  }
  if (!(Test-Path -LiteralPath $SourceDir)) {
    throw @"
Release pack folder not found: $SourceDir
Build it first:
  make release-pack-windows
or:
  installer\windows\one_click.ps1 -Version $Version -BuildReleasePack
"@
  }

  $iscc = Find-InnoIscc $IsccPath
  if (-not $iscc) {
    throw @"
ISCC.exe not found. Install Inno Setup 6 (https://jrsoftware.org/isinfo.php), add ISCC to PATH, or set:
  `$env:BONEMET_ISCC = '<path-to-ISCC.exe>'
"@
  }

  Write-Host "==> Building Setup.exe (Inno Setup)..." -ForegroundColor Cyan
  Write-Host "    ISCC: $iscc" -ForegroundColor DarkGray
  Write-Host "    Source: $SourceDir" -ForegroundColor DarkGray
  # ISCC 控制台输出常用 CR-only；直接 & 调用会导致终端里整段无换行
  Invoke-LoggedNative -FilePath $iscc -ArgumentList @(
    "/DAppVersion=$Version",
    "/DSourceDir=$SourceDir",
    $IssPath
  )

  $setup = Get-BonemetSetupExePath -Version $Version -RepoRoot $root
  if (!(Test-Path -LiteralPath $setup)) {
    throw "Setup.exe not found after compile: $setup"
  }
  return $setup
}
 