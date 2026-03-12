[CmdletBinding()]
param(
    [string]$Device,
    [string]$AdbPath
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
Write-Host "Using adb: $resolvedAdb"

$target = $Device
$devices = @(Get-AdbDeviceLines -AdbPath $resolvedAdb)
if (-not $target) {
    $existingOnline = @($devices | Where-Object { $_.State -eq 'device' -and $_.Serial -match '^(127\.0\.0\.1:\d+|emulator-\d+)$' })
    if ($existingOnline.Count -ge 1) {
        $target = $existingOnline[0].Serial
    }
    else {
        $target = Find-BluestacksEndpoint
        if (-not $target) {
            $started = Start-BluestacksPlayer
            if ($started) {
                Start-Sleep -Seconds 15
                $target = Find-BluestacksEndpoint
                $devices = @(Get-AdbDeviceLines -AdbPath $resolvedAdb)
                $existingOnline = @($devices | Where-Object { $_.State -eq 'device' -and $_.Serial -match '^(127\.0\.0\.1:\d+|emulator-\d+)$' })
                if ($existingOnline.Count -ge 1) {
                    $target = $existingOnline[0].Serial
                }
            }
        }
        if (-not $target) {
            Write-Error "No active BlueStacks endpoint found."
            exit 1
        }
    }
}

$existing = $devices | Where-Object { $_.Serial -eq $target } | Select-Object -First 1
if ($existing -and $existing.State -eq "device") {
    Write-Host "Connected device: $($existing.Serial) [$($existing.State)]"
    exit 0
}

if ($existing -and $existing.State -eq "offline") {
    Write-Error "Endpoint $target is offline. Restart BlueStacks or rerun this script after it stabilizes."
    exit 2
}

if ($target -notmatch "^[^:]+:\d+$") {
    Write-Error "Device override '$target' is not an adb connect endpoint and is not currently online."
    exit 3
}

$connection = Connect-AdbEndpoint -AdbPath $resolvedAdb -Endpoint $target
foreach ($line in $connection.ConnectOutput) {
    if (-not [string]::IsNullOrWhiteSpace($line)) {
        Write-Host $line
    }
}

if ($connection.Device -and $connection.Device.State -eq "device") {
    Write-Host "Connected device: $($connection.Device.Serial) [$($connection.Device.State)]"
    exit 0
}

if ($connection.Device -and $connection.Device.State -eq "offline") {
    Write-Error "Endpoint $target is offline. Restart BlueStacks or rerun this script after it stabilizes."
    exit 2
}

Write-Error "ADB did not report $target as an online device."
exit 4
