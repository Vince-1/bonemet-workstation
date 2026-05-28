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
  function Ensure-Pip([string]$P) {
    try {
      & $P -m pip --version | Out-Null
      return
    } catch {
      $gp = ".\\python\\get-pip.py"
      if (Test-Path $gp) {
        Write-Host "==> Bootstrapping pip (get-pip.py)..." -ForegroundColor Cyan
        & $P $gp
      } else {
        throw "pip not available and get-pip.py not found at $gp"
      }
    }
  }

  try {
    & $Py -c "import nuitka" | Out-Null
    return
  } catch {
    Write-Host "==> Installing Nuitka..." -ForegroundColor Cyan
    Ensure-Pip $Py
    & $Py -m pip install -U pip | Out-Null
    & $Py -m pip install -U nuitka zstandard
  }
}

Ensure-Nuitka $Python

Write-Host "==> Compiling API launcher..." -ForegroundColor Cyan
& $Python -m nuitka --onefile --assume-yes-for-downloads `
  --output-dir=.\bin `
  --output-filename=bonemet-api.exe `
  .\scripts\win_launch_api.py

Write-Host "==> Compiling Worker launcher..." -ForegroundColor Cyan
& $Python -m nuitka --onefile --assume-yes-for-downloads `
  --output-dir=.\bin `
  --output-filename=bonemet-worker.exe `
  .\scripts\win_launch_worker.py

if (!(Test-Path ".\\bin\\bonemet-api.exe") -or !(Test-Path ".\\bin\\bonemet-worker.exe")) {
  throw "Nuitka compilation did not produce expected EXEs under .\\bin"
}
Write-Host "OK: bin\\bonemet-api.exe, bin\\bonemet-worker.exe" -ForegroundColor Green

