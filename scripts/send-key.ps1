[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,

    [int]$RepeatCount = 1,
    [int]$DelayMs = 120,
    [Nullable[long]]$WindowHandle = $null,
    [string]$WindowTitleContains,
    [Nullable[int]]$ExpectedClientWidth = $null,
    [Nullable[int]]$ExpectedClientHeight = $null,
    [Nullable[int]]$FocusRetries = $null,
    [Nullable[int]]$FocusRetryDelayMs = $null,
    [switch]$Json
)

$env:PYTHONPATH = (Join-Path $PSScriptRoot "..\python")
$env:BLUECLAW_SEND_KEY = $Key
$env:BLUECLAW_WINDOW_HANDLE = if ($WindowHandle.HasValue) { "$($WindowHandle.Value)" } else { "" }
$env:BLUECLAW_WINDOW_TITLE_CONTAINS = if ($WindowTitleContains) { $WindowTitleContains } else { "" }
$env:BLUECLAW_EXPECTED_CLIENT_WIDTH = if ($ExpectedClientWidth.HasValue) { "$($ExpectedClientWidth.Value)" } else { "" }
$env:BLUECLAW_EXPECTED_CLIENT_HEIGHT = if ($ExpectedClientHeight.HasValue) { "$($ExpectedClientHeight.Value)" } else { "" }
$env:BLUECLAW_FOCUS_RETRIES = if ($FocusRetries.HasValue) { "$($FocusRetries.Value)" } else { "" }
$env:BLUECLAW_FOCUS_RETRY_DELAY_MS = if ($FocusRetryDelayMs.HasValue) { "$($FocusRetryDelayMs.Value)" } else { "" }
$code = @"
import json
import os

from blueclaw_companion.execution_mode import DesktopOptions, DesktopTarget
from blueclaw_companion.window_control import send_bluestacks_key

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
payload = send_bluestacks_key(
    os.environ["BLUECLAW_SEND_KEY"],
    repeat_count=$RepeatCount,
    delay_ms=$DelayMs,
    target=target,
    options=options,
)
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
    Write-Host ("Sent key {0} x{1}" -f $Key, $RepeatCount)
}
