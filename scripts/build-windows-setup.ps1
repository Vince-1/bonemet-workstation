<#
Build BoneMet Windows Setup.exe (wrapper for installer/windows/build_installer.ps1).

Usage (repo root):
  .\scripts\build-windows-setup.ps1
  .\scripts\build-windows-setup.ps1 -Version 0.2.0
  .\scripts\build-windows-setup.ps1 -Version 0.2.0 -BuildReleasePack
  .\scripts\build-windows-setup.ps1 -Version 0.2.0 -BuildReleasePack -NoModels

Environment:
  BONEMET_VERSION  — default version if -Version omitted
  BONEMET_ISCC     — optional path to ISCC.exe (see installer/windows/_inno.ps1)
  BUNDLE_MODELS    — 0 = 不打模型（等同 -NoModels）
#>

Param(
  [string]$Version = "",
  [string]$IsccPath = "",
  [switch]$BuildReleasePack = $false,
  [switch]$NoModels = $false,
  [string]$BashPath = "bash.exe"
)

$ErrorActionPreference = "Stop"
if (-not $Version) {
  $Version = $env:BONEMET_VERSION
}
if (-not $Version) {
  $Version = "0.2.0"
}

$installer = Join-Path $PSScriptRoot "..\installer\windows\build_installer.ps1"
$params = @{
  Version           = $Version
  BuildReleasePack  = $BuildReleasePack
  NoModels          = $NoModels
  BashPath          = $BashPath
}
if ($IsccPath) { $params.IsccPath = $IsccPath }
if (-not $NoModels -and $env:BUNDLE_MODELS -eq "0") { $params.NoModels = $true }
& $installer @params
