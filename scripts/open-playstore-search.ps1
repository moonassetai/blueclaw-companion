[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Query,

    [string]$Device,
    [string]$AdbPath
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device
$encodedQuery = [System.Uri]::EscapeDataString($Query)
$uri = "market://search?q=$encodedQuery&c=apps"

$result = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @(
    "shell", "am", "start",
    "-a", "android.intent.action.VIEW",
    "-d", $uri
)

Write-Host "Opened Play Store search on $resolvedDevice"
Write-Host "Query: $Query"
foreach ($line in $result.Output) {
    if (-not [string]::IsNullOrWhiteSpace($line)) {
        Write-Host $line
    }
}
