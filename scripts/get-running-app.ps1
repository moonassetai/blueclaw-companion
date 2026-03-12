[CmdletBinding()]
param(
    [string]$Device,
    [string]$AdbPath
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device
$app = Get-ForegroundAppInfo -AdbPath $resolvedAdb -Device $resolvedDevice

Write-Host "Device: $resolvedDevice"
Write-Host "Foreground package: $($app.Package)"
Write-Host "Foreground activity: $($app.Activity)"
Write-Host "Detected via: $($app.Source)"
