[CmdletBinding()]
param(
    [string]$Device,
    [string]$AdbPath,
    [string]$OutputPath = (Join-Path (Get-Location) ("artifacts\ui-{0}.xml" -f (Get-Date -Format "yyyyMMdd-HHmmss")))
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$remotePath = "/sdcard/window_dump.xml"
Ensure-OutputDirectory -Path $resolvedOutput

$dumpResult = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("shell", "uiautomator", "dump", $remotePath)
$pullResult = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("pull", $remotePath, $resolvedOutput)

Write-Host "UI hierarchy saved: $resolvedOutput"
foreach ($line in @($dumpResult.Output) + @($pullResult.Output)) {
    if (-not [string]::IsNullOrWhiteSpace($line)) {
        Write-Host $line
    }
}
