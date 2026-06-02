# Probe BoneMet uninstall registry (debug installer upgrade detection)
$guid = 'B4B0E18E-6E85-4E6E-9A2A-6C8F3A9D4E7B'
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{${guid}}_is1",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{${guid}}_is1",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{${guid}}_is1",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$guid"
)
foreach ($p in $paths) {
    if (Test-Path -LiteralPath $p) {
        Write-Host "FOUND $p"
        Get-ItemProperty -LiteralPath $p | Format-List InstallLocation, DisplayName, UninstallString, QuietUninstallString
    } else {
        Write-Host "missing $p"
    }
}
Write-Host "`n--- HKCU keys matching BoneMet/B4B0 ---"
Get-ChildItem 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall' -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match 'B4B0|BoneMet' } |
    ForEach-Object {
        Write-Host $_.Name
        Get-ItemProperty $_.PSPath | Select-Object InstallLocation, DisplayName, UninstallString
    }
Write-Host "`n--- HKLM keys matching BoneMet/B4B0 ---"
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall' -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match 'B4B0|BoneMet' } |
    ForEach-Object {
        Write-Host $_.Name
        Get-ItemProperty $_.PSPath | Select-Object InstallLocation, DisplayName, UninstallString
    }
