# Mobile Game Learner

`mobile-game-learner` is a small rule-based workflow layer on top of Blueclaw Companion Phase 1 and Phase 2.

It is meant for repetitive mobile-game navigation on a local BlueStacks or Android device without introducing heavy training systems, RL loops, or large new dependencies.

## What it does

For each learning cycle it can:

1. connect to BlueStacks if needed
2. dump the current UI and optionally capture a screenshot
3. classify the screen into one of:
   - `loading`
   - `login`
   - `tutorial`
   - `battle`
   - `reward`
   - `menu`
   - `upgrade`
   - `unknown`
4. choose a conservative next action from a game profile
5. append a JSONL memory entry for later profile refinement

## Files

- `python/blueclaw_companion/game_state.py`
- `python/blueclaw_companion/game_profiles.py`
- `python/blueclaw_companion/action_policy.py`
- `python/blueclaw_companion/workflow_memory.py`
- `python/blueclaw_companion/mobile_game_learner.py`
- `workflows/mobile-game-learner.json`

## Profile model

Each profile defines:

- `package_name`
- `known_state_hints`
- `action_targets`
- `notes`

The generic profile uses label-oriented actions such as `text_match_tap` so the learner can stay portable across games.

## Local usage

From the repo root in PowerShell:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion learner profiles
```

Classify an existing UI dump:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion learner run --profile generic --xml .\artifacts\sample.xml --package com.example.game --json
```

Capture directly from BlueStacks and record a memory entry:

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion learner run --profile generic --capture --connect --json
```

Add `--capture-screenshot --use-ocr` only when XML is not enough.

## Memory

Memory is appended to:

- `artifacts/mobile-game-learner/workflow-memory.jsonl`

Each line stores:

- timestamp
- profile id
- package name
- state and confidence
- suggested action and confidence
- matched hints
- artifact paths

## Limits

- Classification is deterministic and shallow by design.
- `text_match_tap` actions are suggestions only; this layer does not auto-tap yet.
- Games rendered mostly inside opaque engines or webviews may expose little XML text.
- Profiles need manual refinement from real screenshots and UI dumps.
