# RDP Control Guidance (BlueStacks-first)

Blueclaw Companion desktop mode is most reliable in a stable, dedicated desktop session. This file defines the practical operating model.

## Recommended Session Model

- Use a dedicated Windows user/session for automation.
- Keep one fixed desktop resolution (for example `1600x900`).
- Keep display scaling fixed at `100%`.
- Keep BlueStacks on one monitor when possible.
- Keep one primary BlueStacks instance per session unless you use explicit targeting.

## Stable Targeting

For deterministic runs, pass one of:

- `--window-handle <handle>`
- `--window-title-contains "BlueStacks"`

And lock geometry:

- `--expected-client-width <w>`
- `--expected-client-height <h>`

If geometry drifts, desktop actions fail fast instead of clicking the wrong location.

## Foreground and Focus Reality

- Desktop actions internally retry focus.
- Windows can still reject focus in some contexts.
- In RDP, avoid backgrounding/minimizing the automation desktop while actions run.
- Prefer running from the same interactive session that owns the BlueStacks window.

## Capture Reliability

- Primary path: capture BlueStacks client area.
- Fallback path: fullscreen capture when window capture is unavailable and fallback is enabled.
- If fullscreen fallback is undesirable for your runbook, disable it with `--no-desktop-fullscreen-fallback`.

## Practical Runbook

```powershell
$env:PYTHONPATH = "python"
python -m blueclaw_companion learner run --profile generic --capture --control-mode desktop --window-title-contains "BlueStacks" --expected-client-width 1600 --expected-client-height 900 --json
```

```powershell
python -m blueclaw_companion workflow run --workflow open-app --execution-mode desktop --window-title-contains "BlueStacks" --expected-client-width 1600 --expected-client-height 900 --json
```

## Safety Boundaries

- Desktop control is possible; perception remains partial.
- This is not a fully autonomous desktop agent.
- Keep sensitive account, identity, and wallet steps human-gated.
- Use low-risk, reversible actions for unattended loops.
