[CmdletBinding()]
param(
    [string]$Device,
    [string]$AdbPath,
    [string]$ScreenshotPath = (Join-Path (Get-Location) ("artifacts\screen-{0}.png" -f (Get-Date -Format "yyyyMMdd-HHmmss"))),
    [string]$UiDumpPath = (Join-Path (Get-Location) ("artifacts\ui-{0}.xml" -f (Get-Date -Format "yyyyMMdd-HHmmss"))),
    [switch]$AllowUiDumpFailure,
    [int]$UiDumpRetries = 2
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device

# 1. Start App resolution first since it dumps window/activity state
$appInfo = Get-ForegroundAppInfo -AdbPath $resolvedAdb -Device $resolvedDevice

# 2. Dump UI
$resolvedDumpOut = [System.IO.Path]::GetFullPath($UiDumpPath)
$remoteDumpPath = "/sdcard/window_dump.xml"
Ensure-OutputDirectory -Path $resolvedDumpOut
$uiDumpSucceeded = $false
$lastUiDumpError = $null
for ($attempt = 1; $attempt -le ([Math]::Max(1, $UiDumpRetries)); $attempt++) {
    try {
        $dumpResult = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("shell", "uiautomator", "dump", $remoteDumpPath)
        $pullDumpResult = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("pull", $remoteDumpPath, $resolvedDumpOut)
        $uiDumpSucceeded = $true
        break
    }
    catch {
        $lastUiDumpError = $_
        Start-Sleep -Milliseconds 350
    }
}

# 3. Take Screenshot
if ($ScreenshotPath) {
    $resolvedScreenOut = [System.IO.Path]::GetFullPath($ScreenshotPath)
    $remoteScreenPath = "/sdcard/screen.png"
    Ensure-OutputDirectory -Path $resolvedScreenOut
    $screenResult = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("shell", "screencap", "-p", $remoteScreenPath)
    $pullScreenResult = Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("pull", $remoteScreenPath, $resolvedScreenOut)
}

if (-not $uiDumpSucceeded -and -not $AllowUiDumpFailure) {
    throw $lastUiDumpError
}

# The only standard output item should be the foreground package
Write-Host "Foreground Package: $($appInfo.Package)"
