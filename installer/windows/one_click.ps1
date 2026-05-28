<#
One-click build:
  1) (optional) build release-pack folder
  2) (optional) nuitka compile entrypoints (A route)
  3) build Setup.exe via Inno Setup
  4) (optional) sign Setup.exe via signtool

Typical usage (Windows build machine):
  .\installer\windows\one_click.ps1 -Version "0.2.0" -IsccPath "C:\Program Files (x86)\Inno Setup 6\iscc.exe"

With signing:
  .\installer\windows\one_click.ps1 -Version "0.2.0" -IsccPath "...\iscc.exe" -PfxPath ".\cert.pfx" -PfxPassword "****"

Notes:
- If you set -BuildReleasePack, this script expects Git Bash (bash.exe) to exist and can run scripts/build-release-pack.sh.
- Otherwise, prepare dist-release/BoneMet-Workstation-<ver>-win-x64 first (e.g. make release-pack-windows).
#>

Param(
  [Parameter(Mandatory=$true)][string]$Version,
  [Parameter(Mandatory=$true)][string]$IsccPath,
  [switch]$BuildReleasePack = $false,
  [switch]$CompileEntrypoints = $false,
  [string]$BashPath = "bash.exe",
  [string]$Signtool = "signtool.exe",
  [string]$PfxPath = "",
  [string]$PfxPassword = "",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function RepoRoot() {
  return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$root = RepoRoot
$dist = Join-Path $root "dist-release"
$stage = Join-Path $dist ("BoneMet-Workstation-" + $Version + "-win-x64")

if ($BuildReleasePack) {
  Write-Host "==> Building release pack folder..." -ForegroundColor Cyan
  Push-Location $root
  try {
    # Requires bash (Git Bash) on Windows.
    & $BashPath "-lc" "BONEMET_VERSION=$Version BONEMET_TARGET=windows bash scripts/build-release-pack.sh"
  } finally {
    Pop-Location
  }
}

if (!(Test-Path $stage)) {
  throw "Release pack folder not found: $stage`nBuild it first (make release-pack-windows) or pass -BuildReleasePack."
}

if ($CompileEntrypoints) {
  Write-Host "==> Compiling entrypoints (Nuitka)..." -ForegroundColor Cyan
  Push-Location $stage
  try {
    & (Join-Path $root "installer\windows\compile_nuitka.ps1") -Python ".\python\python.exe"
  } finally {
    Pop-Location
  }
}

Write-Host "==> Building Setup.exe (Inno Setup)..." -ForegroundColor Cyan
$iss = Join-Path $root "installer\windows\bonemet.iss"
& $IsccPath "/DAppVersion=$Version" ("/DSourceDir=$stage") $iss

$setup = Join-Path $dist ("BoneMet-Workstation-" + $Version + "-Setup.exe")
if (!(Test-Path $setup)) { throw "Setup.exe not found: $setup" }

if ($PfxPath -ne "") {
  Write-Host "==> Signing Setup.exe..." -ForegroundColor Cyan
  if ($PfxPassword -ne "") {
    & $Signtool sign /fd SHA256 /td SHA256 /tr $TimestampUrl /f $PfxPath /p $PfxPassword $setup
  } else {
    & $Signtool sign /fd SHA256 /td SHA256 /tr $TimestampUrl /f $PfxPath $setup
  }
  & $Signtool verify /pa /v $setup
}

Write-Host "OK: $setup" -ForegroundColor Green

