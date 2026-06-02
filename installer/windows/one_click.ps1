<#
One-click build:
  1) (optional) build release-pack folder
  2) (optional) nuitka compile entrypoints (A route)
  3) build Setup.exe via Inno Setup
  4) (optional) sign Setup.exe via signtool

Typical usage (repo root, Windows):
  .\installer\windows\one_click.ps1 -Version "0.2.0"
  make windows-setup-full BONEMET_VERSION=0.2.0

Custom ISCC (optional):
  $env:BONEMET_ISCC = "D:\Tools\ISCC.exe"
  .\installer\windows\one_click.ps1 -Version "0.2.0"

With signing:
  .\installer\windows\one_click.ps1 -Version "0.2.0" -PfxPath ".\cert.pfx" -PfxPassword "****"
#>

Param(
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$IsccPath = "",
  [switch]$BuildReleasePack = $false,
  [switch]$NoModels = $false,
  [switch]$CompileEntrypoints = $false,
  [string]$BashPath = "bash.exe",
  [string]$Signtool = "signtool.exe",
  [string]$PfxPath = "",
  [string]$PfxPassword = "",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_inno.ps1")

$root = Get-BonemetRepoRoot
$stage = Get-BonemetReleasePackDir -Version $Version -RepoRoot $root
$bundleModels = Get-BonemetBundleModelsFlag -NoModels:$NoModels

if ($BuildReleasePack) {
  Invoke-BonemetReleasePackWindows -Version $Version -BashPath $BashPath -BundleModels $bundleModels
}

if (!(Test-Path -LiteralPath $stage)) {
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

$setup = Invoke-BonemetSetupBuild -Version $Version -IsccPath $IsccPath -SourceDir $stage

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
