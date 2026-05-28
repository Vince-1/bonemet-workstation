Param(
  [string]$Version = "0.2.0",
  [string]$IsccPath = "",
  [switch]$BuildReleasePack = $false,
  [string]$BashPath = "bash.exe"
)

$ErrorActionPreference = "Stop"

function RepoRoot() {
  return (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
}

function Find-Iscc([string]$Candidate) {
  if ($Candidate -and (Test-Path $Candidate)) { return (Resolve-Path $Candidate).Path }
  if ($Candidate -and $Candidate -ieq "iscc.exe") {
    $cmd = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Path }
  }
  $common = @(
    "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
    "C:\\Program Files\\Inno Setup 6\\ISCC.exe",
    "C:\\Program Files (x86)\\Inno Setup 5\\ISCC.exe",
    "C:\\Program Files\\Inno Setup 5\\ISCC.exe"
  )
  foreach ($p in $common) { if (Test-Path $p) { return $p } }
  return ""
}

$root = RepoRoot
$dist = Join-Path $root "dist-release"
$stage = Join-Path $dist ("BoneMet-Workstation-" + $Version + "-win-x64")

if ($BuildReleasePack) {
  Write-Host "==> Building release pack folder..." -ForegroundColor Cyan
  Push-Location $root
  try {
    & $BashPath "-lc" "BONEMET_VERSION=$Version BONEMET_TARGET=windows bash scripts/build-release-pack.sh"
  } finally {
    Pop-Location
  }
}

if (!(Test-Path $stage)) {
  throw "Release pack folder not found: $stage`nBuild it first (make release-pack-windows) or run this script with -BuildReleasePack (requires Git Bash)."
}

Write-Host "==> Building Setup.exe via Inno Setup..." -ForegroundColor Cyan
$iss = Join-Path $PSScriptRoot "bonemet.iss"
$iscc = Find-Iscc $IsccPath
if (!$iscc) {
  throw "ISCC.exe not found. Install Inno Setup 6, or pass -IsccPath 'C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe'."
}
& $iscc "/DAppVersion=$Version" ("/DSourceDir=$stage") $iss

Write-Host "OK: dist-release\BoneMet-Workstation-$Version-Setup.exe" -ForegroundColor Green

