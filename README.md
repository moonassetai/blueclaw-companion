# Blueclaw Companion

Blueclaw Companion is a Windows-first, BlueStacks-first automation companion for MULTIVAC. It handles local Android execution for repetitive mobile tasks, utilizing ADB for robust device control instead of token-heavy reasoning.

It is split into three main layers:
1. **Phase 1 (Scripts)**: Direct ADB and BlueStacks execution primitives.
2. **Phase 2 (Workflows)**: JSON declarative steps to string primitives together.
3. **Mobile Game Learner**: A lightweight python rule-based classifier that chooses and logs the next action for repetitive in-game loops.

There is now also a small **desktop automation layer** for cases where ADB input alone is not enough for BlueStacks/MMORPG interaction. It adds window focus, relative clicks, keyboard sends, and desktop screenshot capture without replacing the existing ADB path.

There is also a lightweight **shortcut acceleration layer** that resolves perception/control backends and prepares future integrations like scrcpy and vision-model classification hooks.

## Prerequisites

- Windows OS
- **BlueStacks 5** (or an equivalent Android emulator running locally)
- Python 3.9+
- Android SDK platform-tools (`adb.exe`) or BlueStacks bundled (`HD-Adb.exe`) installed and available in your shell.

## Setup & BlueStacks / ADB Setup

1. **Enable ADB in BlueStacks**:
   - Open BlueStacks Settings > Advanced > Enable Android Debug Bridge (ADB).
2. **Ensure Python environment**:
   - `python -m venv venv`
   - `.\venv\Scripts\activate`
   - `pip install -r python\requirements.txt` (Phase 2 intentionally runs on the Python standard library!)
3. **Connect to Emulator**:
   - The tooling will automatically probe standard BlueStacks ADB ports (e.g., `127.0.0.1:5555`, `127.0.0.1:5556`) and attempt to connect utilizing Phase 1 scripts.
   - Or connect manually: `adb connect 127.0.0.1:5555` followed by `adb devices`.

## How to Run Phase 1 (Scripts)

Phase 1 scripts are raw PowerShell ADB wrappers located in the `scripts/` folder. They interact directly with the attached device.

```powershell
# Get active app
.\scripts\get-running-app.ps1

# Take a screenshot to artifacts/
.\scripts\screenshot.ps1 -OutputPath .\artifacts\screen.png

# Dump UI hierarchy XML to artifacts/
.\scripts\dump-ui.ps1 -OutputPath .\artifacts\dump.xml

# Perform taps/text
.\scripts\tap.ps1 -X 100 -Y 200
.\scripts\type-text.ps1 -Text "Hello"
```

Desktop-side BlueStacks helpers are also available when you need emulator-window interaction instead of ADB:

```powershell
# Detect and optionally focus the BlueStacks window
.\scripts\focus-bluestacks.ps1

# Send a key to the BlueStacks window
.\scripts\send-key.ps1 -Key "{TAB}" -RepeatCount 2 -DelayMs 100

# Click inside the BlueStacks client area using window-relative pixels
.\scripts\click-window-relative.ps1 -X 300 -Y 500 -RepeatCount 2 -DelayMs 120

# Capture the BlueStacks window, or full screen if needed
.\scripts\capture-window.ps1 -OutputPath .\artifacts\desktop.png -FullScreenFallback

# Deterministic targeting for dedicated sessions
.\scripts\focus-bluestacks.ps1 -WindowTitleContains "BlueStacks" -ExpectedClientWidth 1600 -ExpectedClientHeight 900
```

## How to Run Phase 2 (Workflow Logic)

Phase 2 uses declarative JSON files located in `workflows/` mapped to corresponding python and shell layers.

```powershell
# Must set PYTHONPATH since code is in python/
$env:PYTHONPATH = "python"

# Run a JSON workflow
python -m blueclaw_companion workflow run --workflow open-polymarket-until-market-list

# Run with custom variables
python -m blueclaw_companion workflow run --workflow install-app --var PackageName=com.example.app
```

## How to Run `mobile-game-learner`

The learner layer is a small rule-based classifier built to navigate mobile games via a defined profile. It stores execution memories in `artifacts/mobile-game-learner/workflow-memory.jsonl` which can later be used to refine and improve the play profile algorithmically.

```powershell
$env:PYTHONPATH = "python"

# List available learner profiles
python -m blueclaw_companion learner profiles

# Execute a direct capture and inference loop on the connected BlueStacks instance
python -m blueclaw_companion learner run --profile generic --capture --connect --json

# Use desktop capture/input mode instead of ADB
python -m blueclaw_companion learner run --profile generic --capture --control-mode desktop --window-title-contains "BlueStacks" --expected-client-width 1600 --expected-client-height 900 --use-ocr --json

# Workflow desktop mode (capture path)
python -m blueclaw_companion workflow run --workflow open-app --execution-mode desktop --window-title-contains "BlueStacks" --desktop-fullscreen-fallback --json

# Test inference against existing artifacts without auto-connecting
python -m blueclaw_companion learner run --profile generic --xml .\artifacts\dump.xml --json
```

`--control-mode adb` remains the default. Use `--control-mode desktop` when the game only reacts reliably to the Windows-side BlueStacks window or when you need keyboard-driven actions.

Desktop target options (`learner run`, `learner loop`, `workflow run`):

- `--window-handle`
- `--window-title-contains`
- `--expected-client-width`
- `--expected-client-height`
- `--desktop-fullscreen-fallback` / `--no-desktop-fullscreen-fallback`

Env fallback keys:

- `BLUECLAW_WINDOW_HANDLE`
- `BLUECLAW_WINDOW_TITLE_CONTAINS`
- `BLUECLAW_EXPECTED_CLIENT_WIDTH`
- `BLUECLAW_EXPECTED_CLIENT_HEIGHT`
- `BLUECLAW_DESKTOP_FULLSCREEN_FALLBACK`

## Repository Organization & Artifacts Behavior

- `python/` - Core Python codebase (`blueclaw_companion` CLI module including Phase 2 workflow engine and the `mobile-game-learner`). 
- `scripts/` - Phase 1 PowerShell ADB execution modules.
- `workflows/` - Phase 2 declarative JSON template workflows.
- `references/` - Playbooks and conceptual documentation.
- `artifacts/` - Temporary output directory for `xml` UI dumps, `png` screenshots, and `jsonl` workflow memories. **Automatically created during execution and should be ignored by Git.** Safe to delete between runs.

## Desktop Automation Notes

- What it solves: emulator-window focus issues, desktop keyboard input, and desktop screenshot capture when ADB-only interaction is not enough for MMORPG loops.
- What it does not solve: reliable UI hierarchy access on desktop mode, precise OCR-based clicking, or full autonomous gameplay.
- Reference: `references/desktop-automation.md`
- RDP guidance: `references/rdp-control.md`

## Shortcut Acceleration Notes

- Backend abstraction files:
  - `python/blueclaw_companion/perception_backends.py`
  - `python/blueclaw_companion/control_backends.py`
  - `python/blueclaw_companion/shortcuts.py`
- Current active backends:
  - perception: `adb_ui_dump`, `desktop_capture`, optional `ocr_tesseract`
  - control: `adb`, `desktop`
- Future hooks (placeholder only):
  - perception: `vision_model`
  - control: `scrcpy`

Inspect resolved shortcut plan locally:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion shortcuts status --mode adb --use-ocr --prefer-scrcpy --prefer-vision-model --json
```

Reference: `references/shortcut-acceleration.md`
