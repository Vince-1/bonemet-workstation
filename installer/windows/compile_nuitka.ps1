<#
Compile Python entrypoints to EXE (optional hardening).

This is an *advanced* step and should run on a Windows build machine.
It does NOT replace pip install; it only hides Python sources and provides nicer entrypoints.

Prereqs:
  pip install -U nuitka zstandard

Suggested usage:
  1) Build release pack folder first (dist-release/BoneMet-Workstation-<ver>-win-x64)
  2) cd into that folder
  3) run this script to create bin\bonemet-api.exe and bin\bonemet-worker.exe
  4) Update scripts\win-run-*.bat to prefer the exe if present (already supported by this repo if you wire it)
#>

Param(
  [string]$Python = ".\python\python.exe"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path ".\bin" | Out-Null

function Ensure-Nuitka([string]$Py) {
  function Assert-Ok([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit=$LASTEXITCODE)" }
  }

  function Ensure-Pip([string]$P) {
    & $P -m pip --version *> $null
    if ($LASTEXITCODE -eq 0) { return }

    $gp = ".\\python\\get-pip.py"
    if (!(Test-Path $gp)) {
      throw "pip not available and get-pip.py not found at $gp"
    }
    Write-Host "==> Bootstrapping pip (get-pip.py)..." -ForegroundColor Cyan
    & $P $gp
    Assert-Ok "get-pip.py"

    & $P -m pip --version *> $null
    Assert-Ok "pip --version"
  }

  & $Py -c "import nuitka" *> $null
  if ($LASTEXITCODE -eq 0) { return }

  Write-Host "==> Installing Nuitka..." -ForegroundColor Cyan
  Ensure-Pip $Py
  & $Py -m pip install -U pip *> $null
  Assert-Ok "pip install -U pip"
  & $Py -m pip install -U nuitka zstandard
  Assert-Ok "pip install nuitka"
}

Ensure-Nuitka $Python

function Ensure-Exe([string]$ExpectedPath, [string]$HintGlob) {
  if (Test-Path $ExpectedPath) { return }

  $bin = Resolve-Path ".\\bin"
  $candidates = @()
  try {
    $candidates += Get-ChildItem -Path $bin -Filter "*.exe" -ErrorAction SilentlyContinue
  } catch {}
  try {
    $candidates += Get-ChildItem -Path "." -Filter "*.exe" -ErrorAction SilentlyContinue
  } catch {}
  if ($HintGlob) {
    try { $candidates += Get-ChildItem -Path $bin -Filter $HintGlob -ErrorAction SilentlyContinue } catch {}
    try { $candidates += Get-ChildItem -Path "." -Filter $HintGlob -ErrorAction SilentlyContinue } catch {}
  }
  $cand = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($cand -and (Test-Path $cand.FullName)) {
    Move-Item -Force $cand.FullName $ExpectedPath
  }

  if (!(Test-Path $ExpectedPath)) {
    Write-Host "==> Debug: .\\bin contents" -ForegroundColor Yellow
    Get-ChildItem -Path ".\\bin" -Force | Format-Table -AutoSize | Out-String | Write-Host
    throw "Nuitka compilation did not produce expected EXE: $ExpectedPath"
  }
}

Write-Host "==> Compiling API launcher..." -ForegroundColor Cyan
& $Python -m nuitka --onefile --assume-yes-for-downloads `
  --output-dir=.\bin `
  --output-filename=bonemet-api.exe `
  .\scripts\win_launch_api.py
Ensure-Exe ".\\bin\\bonemet-api.exe" "*api*.exe"

Write-Host "==> Compiling Worker launcher..." -ForegroundColor Cyan
& $Python -m nuitka --onefile --assume-yes-for-downloads `
  --output-dir=.\bin `
  --output-filename=bonemet-worker.exe `
  .\scripts\win_launch_worker.py
Ensure-Exe ".\\bin\\bonemet-worker.exe" "*worker*.exe"

Write-Host "OK: bin\\bonemet-api.exe, bin\\bonemet-worker.exe" -ForegroundColor Green

