# Phase 2 Architecture

Blueclaw Companion Phase 2 keeps the Windows PowerShell control scripts from Phase 1 and adds a lean Python decision layer on top.

## Layout

- `scripts/*.ps1`
  - Still the execution surface for BlueStacks control.
  - Python workflows shell out to these scripts instead of replacing them.
- `python/blueclaw_companion/ui_dump_parser.py`
  - Parses `uiautomator dump` XML.
  - Extracts visible text, package names, bounds, and simple node metadata.
- `python/blueclaw_companion/state_classifier.py`
  - Deterministic rules for named screen states.
  - XML-first. OCR is optional and treated as a secondary signal.
- `python/blueclaw_companion/screen_analysis.py`
  - Orchestrates XML parsing, optional OCR, and state classification.
- `python/blueclaw_companion/workflow_runner.py`
  - Loads explicit workflow JSON files.
  - Executes Phase 1 scripts.
  - Captures screenshot/XML artifacts, classifies the screen, and chooses the next step.
- `workflows/*.json`
  - Explicit rule-based workflow definitions.
  - No hidden planner or autonomous loop logic.

## Screen Classification

Current classification is designed to be useful without OCR:

1. Read a UI dump XML when available.
2. Extract visible `text` and `content-desc` values.
3. Collect package hints from node metadata and the foreground app query.
4. Match against explicit rules for:
   - `playstore_search`
   - `playstore_app_page`
   - `metamask_onboarding`
   - `metamask_sign_screen`
   - `polymarket_market_list`
   - `game_login`
   - `game_tutorial`
   - `unknown`

OCR is only a hook right now. If `tesseract` is installed and `--use-ocr` is passed, the classifier also considers OCR text. If not, XML-only classification still works.

## Workflow Model

Phase 2 workflows are intentionally small and explicit. Supported step types:

- `script`
  - Run an existing PowerShell control script.
- `capture_and_classify`
  - Save a screenshot and UI dump, query the foreground package, and classify the screen.
- `branch_on_state`
  - Route to the next step based on the current classified state.
- `tap_ui_text`
  - Find a visible XML node by label and tap its bounds center through `tap.ps1`.
- `approval_required`
  - Stop unless the user explicitly allows the workflow to pass a boundary.
- `stop`
  - End the workflow with an explicit message.

## Local Run Commands

From the repo root in PowerShell:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion classify --xml .\artifacts\sample.xml --package com.android.vending
```

Example workflow run:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion workflow run --workflow open-app --var package=com.nexon.ma
```

Dry-run a workflow to see the next mutating step without driving BlueStacks:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion workflow run --workflow install-app --var package=com.nexon.ma --var app_name="MapleStory Idle" --dry-run
```

## Practical Limits

- Webviews can still defeat XML-driven control.
- OCR is optional and not tuned yet.
- There is no image-template matching in Phase 2.
- Workflows remain intentionally conservative around wallet and signing screens.
- Real-world app packages can vary; workflows expose package variables so you can override them.
