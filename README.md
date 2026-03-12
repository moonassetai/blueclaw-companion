# Blueclaw Companion

Blueclaw Companion is a Windows-first, BlueStacks-first automation companion for MULTIVAC. It handles local Android execution for repetitive mobile tasks, utilizing ADB for robust device control instead of token-heavy reasoning.

It is split into three main layers:
1. **Phase 1 (Scripts)**: Direct ADB and BlueStacks execution primitives.
2. **Phase 2 (Workflows)**: JSON declarative steps to string primitives together.
3. **Mobile Game Learner**: A lightweight python rule-based classifier that chooses and logs the next action for repetitive in-game loops.

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

# Test inference against existing artifacts without auto-connecting
python -m blueclaw_companion learner run --profile generic --xml .\artifacts\dump.xml --json
```

## Repository Organization & Artifacts Behavior

- `python/` - Core Python codebase (`blueclaw_companion` CLI module including Phase 2 workflow engine and the `mobile-game-learner`). 
- `scripts/` - Phase 1 PowerShell ADB execution modules.
- `workflows/` - Phase 2 declarative JSON template workflows.
- `references/` - Playbooks and conceptual documentation.
- `artifacts/` - Temporary output directory for `xml` UI dumps, `png` screenshots, and `jsonl` workflow memories. **Automatically created during execution and should be ignored by Git.** Safe to delete between runs.
