[CmdletBinding()]
param(
    [string]$Device,
    [string]$AdbPath,
    [string]$OutputPath = (Join-Path (Get-Location) ("artifacts\screenshot-{0}.png" -f (Get-Date -Format "yyyyMMdd-HHmmss")))
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$remotePath = "/sdcard/blueclaw-screencap.png"
Ensure-OutputDirectory -Path $resolvedOutput

Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("shell", "screencap", "-p", $remotePath) | Out-Null
Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("pull", $remotePath, $resolvedOutput) | Out-Null
Write-Host "Screenshot saved: $resolvedOutput"
