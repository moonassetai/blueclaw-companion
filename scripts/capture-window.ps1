[CmdletBinding()]
param(
    [string]$OutputPath = (Join-Path (Get-Location) ("artifacts\\desktop-{0}.png" -f (Get-Date -Format "yyyyMMdd-HHmmss"))),
    [switch]$FullScreenFallback,
    [Nullable[long]]$WindowHandle = $null,
    [string]$WindowTitleContains,
    [Nullable[int]]$ExpectedClientWidth = $null,
    [Nullable[int]]$ExpectedClientHeight = $null,
    [switch]$Json
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$directory = Split-Path -Path $resolvedOutput -Parent
if ($directory) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$env:PYTHONPATH = (Join-Path $PSScriptRoot "..\python")
$env:BLUECLAW_WINDOW_HANDLE = if ($WindowHandle.HasValue) { "$($WindowHandle.Value)" } else { "" }
$env:BLUECLAW_WINDOW_TITLE_CONTAINS = if ($WindowTitleContains) { $WindowTitleContains } else { "" }
$env:BLUECLAW_EXPECTED_CLIENT_WIDTH = if ($ExpectedClientWidth.HasValue) { "$($ExpectedClientWidth.Value)" } else { "" }
$env:BLUECLAW_EXPECTED_CLIENT_HEIGHT = if ($ExpectedClientHeight.HasValue) { "$($ExpectedClientHeight.Value)" } else { "" }
$code = @"
import json
import os

from blueclaw_companion.execution_mode import DesktopOptions, DesktopTarget
from blueclaw_companion.window_control import detect_bluestacks_window, validate_window_geometry

def parse_int(name):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return int(raw.strip())

target = DesktopTarget(
    window_handle=parse_int("BLUECLAW_WINDOW_HANDLE"),
    window_title_contains=os.environ.get("BLUECLAW_WINDOW_TITLE_CONTAINS") or None,
)
options = DesktopOptions(
    expected_client_width=parse_int("BLUECLAW_EXPECTED_CLIENT_WIDTH"),
    expected_client_height=parse_int("BLUECLAW_EXPECTED_CLIENT_HEIGHT"),
)
window = detect_bluestacks_window(target=target)
if window:
    window = validate_window_geometry(window, options=options)
payload = {
    "window": window.to_dict() if window else None,
    "target": target.to_dict(),
    "options": options.to_dict(),
}
print(json.dumps(payload, separators=(",", ":")))
"@

$windowJson = $code | python -
if ($LASTEXITCODE -ne 0) {
    throw ($windowJson | Out-String).Trim()
}

$windowPayload = if ($windowJson) { $windowJson | ConvertFrom-Json } else { $null }
$window = if ($windowPayload) { $windowPayload.window } else { $null }
$captureMode = "window"

if ($window -and -not $window.is_minimized -and $window.client_width -gt 0 -and $window.client_height -gt 0) {
    $left = [int]$window.client_left
    $top = [int]$window.client_top
    $width = [int]$window.client_width
    $height = [int]$window.client_height
}
elseif ($FullScreenFallback) {
    $captureMode = "fullscreen"
    $left = [System.Windows.Forms.SystemInformation]::VirtualScreen.Left
    $top = [System.Windows.Forms.SystemInformation]::VirtualScreen.Top
    $width = [System.Windows.Forms.SystemInformation]::VirtualScreen.Width
    $height = [System.Windows.Forms.SystemInformation]::VirtualScreen.Height
    $window = $null
}
else {
    throw "BlueStacks window is minimized or unavailable, and fullscreen fallback was not requested."
}

$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($left, $top, 0, 0, $bitmap.Size)
    $bitmap.Save($resolvedOutput, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

$payload = [ordered]@{
    output_path = $resolvedOutput
    capture_mode = $captureMode
    window = $window
    target = if ($windowPayload) { $windowPayload.target } else { $null }
    options = if ($windowPayload) { $windowPayload.options } else { $null }
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 4 -Compress
}
else {
    Write-Host ("Captured {0} to {1}" -f $captureMode, $resolvedOutput)
}
