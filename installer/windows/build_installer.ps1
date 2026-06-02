Param(
  [string]$Version = "0.2.0",
  [string]$IsccPath = "",
  [switch]$BuildReleasePack = $false,
  [switch]$NoModels = $false,
  [string]$BashPath = "bash.exe"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_inno.ps1")

$root = Get-BonemetRepoRoot
$stage = Get-BonemetReleasePackDir -Version $Version -RepoRoot $root
$bundleModels = Get-BonemetBundleModelsFlag -NoModels:$NoModels

if ($BuildReleasePack) {
  Invoke-BonemetReleasePackWindows -Version $Version -BashPath $BashPath -BundleModels $bundleModels
}

$setup = Invoke-BonemetSetupBuild -Version $Version -IsccPath $IsccPath -SourceDir $stage
Write-Host "OK: $setup" -ForegroundColor Green
