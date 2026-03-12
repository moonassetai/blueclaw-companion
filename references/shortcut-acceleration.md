# Shortcut Acceleration Layer

Blueclaw Companion now includes a lightweight shortcut layer that makes it easier to plug in practical helpers without rewriting the core ADB/desktop architecture.

## Why This Exists

- Keep current ADB + desktop paths stable.
- Add clean backend contracts for perception and control.
- Enable incremental adoption of OCR, scrcpy-style workflows, and future vision-model hooks.

## New Modules

- `python/blueclaw_companion/perception_backends.py`
- `python/blueclaw_companion/control_backends.py`
- `python/blueclaw_companion/shortcuts.py`

## Backend Abstraction

Perception backends:

- `adb_ui_dump` (active)
- `desktop_capture` (active)
- `ocr_tesseract` (active when available)
- `vision_model` (placeholder hook)

Control backends:

- `adb` (active)
- `desktop` (active)
- `scrcpy` (placeholder/discoverable)

The learner and workflow layers now resolve backend plans first, then run existing behavior through that plan.

## Implemented Now vs Placeholder

Implemented now:

- Existing ADB capture/control continues unchanged.
- Existing desktop capture/control continues unchanged.
- OCR preference resolves cleanly and enables Tesseract only when available.
- Shortcut capability summary is available through CLI.

Placeholder hooks:

- `vision_model` perception backend: declared and selectable as a future hook, not executing model inference yet.
- `scrcpy` control backend: availability detected and recorded, not used as an active control path yet.

## Practical Usage

Check current shortcut/backend resolution:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion shortcuts status --mode desktop --use-ocr --prefer-scrcpy --prefer-vision-model --json
```

Recommended current stack:

- Default automation: `adb_ui_dump` + `adb`.
- BlueStacks-heavy loops: `desktop_capture` + `desktop`.
- OCR: enable `--use-ocr` and install Tesseract when needed.

## Boundaries

- No heavy CV or RL stack added.
- No claim of full autonomous desktop/game intelligence.
- Sensitive actions should stay bounded and human-gated.
