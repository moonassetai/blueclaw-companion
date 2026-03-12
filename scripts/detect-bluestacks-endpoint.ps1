[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int[]]$Ports = @(5555, 5554, 5556, 5557, 5558, 5559, 5560, 5561, 5562, 5563, 5564, 5565)
)

. "$PSScriptRoot/common.ps1"

$endpoint = Find-BluestacksEndpoint -HostAddress $HostAddress -Ports $Ports
if (-not $endpoint) {
    Write-Error "No active BlueStacks ADB endpoint found on $HostAddress. Checked ports: $($Ports -join ', ')"
    exit 1
}

Write-Host "Detected BlueStacks endpoint: $endpoint"
