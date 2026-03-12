[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Package,

    [string]$Device,
    [string]$AdbPath
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device
$uri = "market://details?id=$Package"

$result = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @(
    "shell", "am", "start",
    "-a", "android.intent.action.VIEW",
    "-d", $uri
)

Write-Host "Opened Play Store details on $resolvedDevice"
Write-Host "Package: $Package"
foreach ($line in $result.Output) {
    if (-not [string]::IsNullOrWhiteSpace($line)) {
        Write-Host $line
    }
}
