Param(
  [Parameter(Mandatory=$true)][string]$Version,
  [string]$Signtool = "signtool.exe",
  [Parameter(Mandatory=$true)][string]$PfxPath,
  [Parameter(Mandatory=$false)][string]$PfxPassword = "",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

$setup = Resolve-Path "$PSScriptRoot\..\..\dist-release\BoneMet-Workstation-$Version-Setup.exe"

Write-Host "==> Signing $setup" -ForegroundColor Cyan

if ($PfxPassword -ne "") {
  & $Signtool sign /fd SHA256 /td SHA256 /tr $TimestampUrl /f $PfxPath /p $PfxPassword $setup
} else {
  & $Signtool sign /fd SHA256 /td SHA256 /tr $TimestampUrl /f $PfxPath $setup
}

& $Signtool verify /pa /v $setup
Write-Host "OK: signed" -ForegroundColor Green

