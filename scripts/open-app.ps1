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
$result = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @(
    "shell", "monkey",
    "-p", $Package,
    "-c", "android.intent.category.LAUNCHER",
    "1"
)

Write-Host "Launch requested for package $Package on $resolvedDevice"
foreach ($line in $result.Output) {
    if (-not [string]::IsNullOrWhiteSpace($line)) {
        Write-Host $line
    }
}
