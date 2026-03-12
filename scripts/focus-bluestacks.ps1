[CmdletBinding()]
param(
    [Nullable[long]]$WindowHandle = $null,
    [string]$WindowTitleContains,
    [Nullable[int]]$ExpectedClientWidth = $null,
    [Nullable[int]]$ExpectedClientHeight = $null,
    [Nullable[int]]$FocusRetries = $null,
    [Nullable[int]]$FocusRetryDelayMs = $null,
    [switch]$NoActivate,
    [switch]$Json
)

$env:PYTHONPATH = (Join-Path $PSScriptRoot "..\python")
$env:BLUECLAW_WINDOW_HANDLE = if ($WindowHandle.HasValue) { "$($WindowHandle.Value)" } else { "" }
$env:BLUECLAW_WINDOW_TITLE_CONTAINS = if ($WindowTitleContains) { $WindowTitleContains } else { "" }
$env:BLUECLAW_EXPECTED_CLIENT_WIDTH = if ($ExpectedClientWidth.HasValue) { "$($ExpectedClientWidth.Value)" } else { "" }
$env:BLUECLAW_EXPECTED_CLIENT_HEIGHT = if ($ExpectedClientHeight.HasValue) { "$($ExpectedClientHeight.Value)" } else { "" }
$env:BLUECLAW_FOCUS_RETRIES = if ($FocusRetries.HasValue) { "$($FocusRetries.Value)" } else { "" }
$env:BLUECLAW_FOCUS_RETRY_DELAY_MS = if ($FocusRetryDelayMs.HasValue) { "$($FocusRetryDelayMs.Value)" } else { "" }
$pythonNoActivate = if ($NoActivate) { "True" } else { "False" }
$pythonActivated = if ($NoActivate) { "False" } else { "True" }
$code = @"
import json
import os

from blueclaw_companion.execution_mode import DesktopOptions, DesktopTarget
from blueclaw_companion.window_control import (
    detect_bluestacks_window,
    focus_bluestacks_window,
    get_window_geometry,
    to_jsonable,
    validate_window_geometry,
)

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
    focus_retries=parse_int("BLUECLAW_FOCUS_RETRIES") or 3,
    focus_retry_delay_ms=parse_int("BLUECLAW_FOCUS_RETRY_DELAY_MS") or 120,
)

window = detect_bluestacks_window(target=target) if $pythonNoActivate else focus_bluestacks_window(target=target, options=options)
if window is None:
    raise SystemExit("No BlueStacks window with a visible main handle was found.")
window = validate_window_geometry(window, options=options)
payload = {
    "window": to_jsonable(window),
    "geometry": get_window_geometry(window),
    "target": target.to_dict(),
    "options": options.to_dict(),
    "activated": $pythonActivated,
}
print(json.dumps(payload, separators=(",", ":")))
"@

$output = $code | python -
if ($LASTEXITCODE -ne 0) {
    throw ($output | Out-String).Trim()
}

if ($Json) {
    $output
}
else {
    $payload = $output | ConvertFrom-Json
    Write-Host ("BlueStacks: {0} ({1})" -f $payload.window.title, $payload.window.process_name)
    Write-Host ("Handle: {0}" -f $payload.window.handle)
    Write-Host ("Client bounds: {0},{1} {2}x{3}" -f $payload.window.client_left, $payload.window.client_top, $payload.window.client_width, $payload.window.client_height)
    Write-Host ("Activated: {0}" -f $payload.activated)
}
