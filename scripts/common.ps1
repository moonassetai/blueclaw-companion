Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Host $Message
}

function Get-AdbCandidates {
    [CmdletBinding()]
    param()

    $candidates = [System.Collections.Generic.List[string]]::new()

    $envPaths = @(
        (Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"),
        (Join-Path $env:USERPROFILE "AppData\Local\Android\Sdk\platform-tools\adb.exe"),
        (Join-Path $env:ANDROID_SDK_ROOT "platform-tools\adb.exe"),
        (Join-Path $env:ANDROID_HOME "platform-tools\adb.exe"),
        "C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
    )

    foreach ($path in $envPaths) {
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }

        if ((Test-Path $path) -and -not $candidates.Contains($path)) {
            $null = $candidates.Add($path)
        }
    }

    return $candidates
}

function Resolve-AdbPath {
    [CmdletBinding()]
    param(
        [string]$AdbPath
    )

    if ($AdbPath) {
        if (-not (Test-Path $AdbPath)) {
            throw "ADB binary not found at: $AdbPath"
        }

        return (Resolve-Path $AdbPath).Path
    }

    $candidates = Get-AdbCandidates
    if ($candidates.Count -eq 0) {
        throw "No adb binary found. Install Android SDK platform-tools or BlueStacks."
    }

    return $candidates[0]
}

function Test-TcpPort {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$HostAddress,

        [Parameter(Mandatory = $true)]
        [int]$Port,

        [int]$TimeoutMs = 400
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostAddress, $Port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $wait) {
            return $false
        }

        $client.EndConnect($async) | Out-Null
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Get-BluestacksLikelyPorts {
    [CmdletBinding()]
    param()

    return @(5555, 5554, 5556, 5557, 5558, 5559, 5560, 5561, 5562, 5563, 5564, 5565)
}

function Find-BluestacksEndpoint {
    [CmdletBinding()]
    param(
        [string]$HostAddress = "127.0.0.1",
        [int[]]$Ports = (Get-BluestacksLikelyPorts)
    )

    foreach ($port in $Ports) {
        if (Test-TcpPort -HostAddress $HostAddress -Port $port) {
            return "${HostAddress}:$port"
        }
    }

    return $null
}

function Invoke-Adb {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$IgnoreExitCode
    )

    $output = & $AdbPath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if (-not $IgnoreExitCode -and $exitCode -ne 0) {
        $joined = $Arguments -join " "
        $body = ($output | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($body)) {
            $body = "adb exited with code $exitCode."
        }

        throw "adb $joined failed: $body"
    }

    [pscustomobject]@{
        Output = @($output)
        ExitCode = $exitCode
    }
}

function Get-AdbDeviceLines {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath
    )

    $result = Invoke-Adb -AdbPath $AdbPath -Arguments @("devices")
    $devices = foreach ($line in $result.Output) {
        $text = [string]$line
        if ($text -match "^(?<serial>\S+)\s+(?<state>device|offline|unauthorized)$") {
            [pscustomobject]@{
                Serial = $matches.serial
                State = $matches.state
            }
        }
    }

    return @($devices)
}

function Connect-AdbEndpoint {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath,

        [Parameter(Mandatory = $true)]
        [string]$Endpoint
    )

    $connectResult = Invoke-Adb -AdbPath $AdbPath -Arguments @("connect", $Endpoint) -IgnoreExitCode
    Start-Sleep -Milliseconds 500

    $devices = Get-AdbDeviceLines -AdbPath $AdbPath
    $target = $devices | Where-Object { $_.Serial -eq $Endpoint } | Select-Object -First 1

    return [pscustomobject]@{
        Endpoint = $Endpoint
        ConnectOutput = ($connectResult.Output | ForEach-Object { [string]$_ })
        Device = $target
        Devices = $devices
    }
}

function Resolve-Device {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath,

        [string]$Device
    )

    if ($Device) {
        return $Device
    }

    $devices = Get-AdbDeviceLines -AdbPath $AdbPath
    $online = @($devices | Where-Object { $_.State -eq "device" })
    $localOnline = @($online | Where-Object { $_.Serial -match "^(127\.0\.0\.1:\d+|emulator-\d+)$" })
    if ($localOnline.Count -eq 1) {
        return $localOnline[0].Serial
    }

    if ($online.Count -eq 1) {
        return $online[0].Serial
    }

    $endpoint = Find-BluestacksEndpoint
    if (-not $endpoint) {
        throw "No active BlueStacks ADB endpoint found."
    }

    $connection = Connect-AdbEndpoint -AdbPath $AdbPath -Endpoint $endpoint
    if ($connection.Device -and $connection.Device.State -eq "device") {
        return $connection.Endpoint
    }

    if ($connection.Device -and $connection.Device.State -eq "offline") {
        throw "BlueStacks endpoint $endpoint is offline. Restart BlueStacks or reconnect."
    }

    throw "Detected BlueStacks endpoint $endpoint, but adb could not bring it online."
}

function Invoke-AdbOnDevice {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath,

        [Parameter(Mandatory = $true)]
        [string]$Device,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$IgnoreExitCode
    )

    return Invoke-Adb -AdbPath $AdbPath -Arguments @("-s", $Device) + $Arguments -IgnoreExitCode:$IgnoreExitCode
}

function Ensure-OutputDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }
}

function ConvertTo-AndroidInputText {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    $escaped = $Text.Replace("\", "\\")
    $escaped = $escaped.Replace(" ", "%s")
    $escaped = $escaped.Replace("&", "\&")
    $escaped = $escaped.Replace("(", "\(")
    $escaped = $escaped.Replace(")", "\)")
    $escaped = $escaped.Replace("<", "\<")
    $escaped = $escaped.Replace(">", "\>")
    $escaped = $escaped.Replace("|", "\|")
    $escaped = $escaped.Replace(";", "\;")
    return $escaped
}

function Get-ForegroundAppInfo {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath,

        [Parameter(Mandatory = $true)]
        [string]$Device
    )

    $windowDump = Invoke-AdbOnDevice -AdbPath $AdbPath -Device $Device -Arguments @("shell", "dumpsys", "window", "windows")
    $windowText = ($windowDump.Output | Out-String)

    $patterns = @(
        "mCurrentFocus.+\s(?<component>[A-Za-z0-9._$]+\/[A-Za-z0-9._$/]+)\}",
        "mFocusedApp.+\s(?<component>[A-Za-z0-9._$]+\/[A-Za-z0-9._$/]+)\s"
    )

    foreach ($pattern in $patterns) {
        if ($windowText -match $pattern) {
            $component = $matches.component
            $parts = $component.Split("/", 2)
            return [pscustomobject]@{
                Package = $parts[0]
                Activity = $parts[1]
                Component = $component
                Source = "dumpsys window"
            }
        }
    }

    $activityDump = Invoke-AdbOnDevice -AdbPath $AdbPath -Device $Device -Arguments @("shell", "dumpsys", "activity", "top")
    $activityText = ($activityDump.Output | Out-String)
    if ($activityText -match "ACTIVITY\s+(?<component>[A-Za-z0-9._$]+\/[A-Za-z0-9._$/]+)") {
        $component = $matches.component
        $parts = $component.Split("/", 2)
        return [pscustomobject]@{
            Package = $parts[0]
            Activity = $parts[1]
            Component = $component
            Source = "dumpsys activity"
        }
    }

    throw "Could not determine the foreground package/activity."
}
