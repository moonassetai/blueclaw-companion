[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Text,

    [string]$Device,
    [string]$AdbPath
)

. "$PSScriptRoot/common.ps1"

$resolvedAdb = Resolve-AdbPath -AdbPath $AdbPath
$resolvedDevice = Resolve-Device -AdbPath $resolvedAdb -Device $Device
$encodedText = ConvertTo-AndroidInputText -Text $Text
Invoke-AdbOnDevice -AdbPath $resolvedAdb -Device $resolvedDevice -Arguments @("shell", "input", "text", $encodedText) | Out-Null

Write-Host "Sent text input to $resolvedDevice"
