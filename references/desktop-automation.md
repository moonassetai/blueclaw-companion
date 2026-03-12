# Desktop Automation for BlueStacks

Blueclaw Companion keeps ADB as the default execution path and adds a focused desktop execution path for BlueStacks-heavy flows.

## What Desktop Mode Covers

- Detect/focus a BlueStacks window with deterministic targeting options.
- Send keyboard input to BlueStacks with bounded repeats.
- Click window-relative client coordinates with bounded repeats.
- Capture BlueStacks client output with fullscreen fallback.
- Return window and geometry metadata for learner/workflow decisions.

## Control Surfaces

PowerShell scripts:

```powershell
.\scripts\focus-bluestacks.ps1
.\scripts\send-key.ps1 -Key "{TAB}" -RepeatCount 2 -DelayMs 100
.\scripts\click-window-relative.ps1 -X 300 -Y 500 -RepeatCount 2 -DelayMs 120
.\scripts\capture-window.ps1 -OutputPath .\artifacts\desktop.png -FullScreenFallback
```

Deterministic targeting options (all desktop scripts):

- `-WindowHandle <int64>`
- `-WindowTitleContains "<substring>"`
- `-ExpectedClientWidth <int>`
- `-ExpectedClientHeight <int>`

Optional focus tuning (`focus-bluestacks.ps1`, `send-key.ps1`, `click-window-relative.ps1`):

- `-FocusRetries <int>`
- `-FocusRetryDelayMs <int>`

## CLI Integration

Learner and workflow commands accept desktop targeting options with CLI priority and env fallback.

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion learner run --profile generic --capture --control-mode desktop --window-title-contains "BlueStacks" --expected-client-width 1600 --expected-client-height 900 --json

python -m blueclaw_companion workflow run --workflow open-app --execution-mode desktop --window-title-contains "BlueStacks" --desktop-fullscreen-fallback --json
```

Env fallback keys:

- `BLUECLAW_WINDOW_HANDLE`
- `BLUECLAW_WINDOW_TITLE_CONTAINS`
- `BLUECLAW_EXPECTED_CLIENT_WIDTH`
- `BLUECLAW_EXPECTED_CLIENT_HEIGHT`
- `BLUECLAW_DESKTOP_FULLSCREEN_FALLBACK`
- `BLUECLAW_FOCUS_RETRIES`
- `BLUECLAW_FOCUS_RETRY_DELAY_MS`

## Safety and Limits

- Desktop mode does not provide Android XML UI dumps.
- `tap_ui_text` and `text_match_tap` remain XML-dependent and are not auto-resolved in desktop mode.
- OCR remains optional and partial; there is no heavy CV stack.
- Focus can still be blocked by Windows foreground rules in some contexts.
- Use conservative, bounded actions for any irreversible or account-adjacent flow.

For dedicated session setup and reliability tuning, see [references/rdp-control.md](/c:/Users/문명철/Documents/APPS/blueclaw-companion/references/rdp-control.md).
