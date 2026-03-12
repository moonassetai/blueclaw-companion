---
name: blueclaw-companion
description: Control BlueStacks and Android app workflows through ADB for repetitive local mobile automation. Use when connecting to BlueStacks, recovering emulator ports after restart, launching apps, installing apps from Google Play, taking screenshots, dumping UI hierarchy, parsing visible controls, or running cautious tap/text/swipe flows for emulator-based tasks and lightweight game/app automation. Do not use for storing secrets, bypassing account security, or fully autonomous handling of sensitive identity, wallet, or verification steps.
---

# Blueclaw Companion

Use this skill to operate BlueStacks as a local Android execution surface for MULTIVAC.

## Core rules

- Prefer local ADB control over token-heavy reasoning.
- Detect the active emulator endpoint before assuming a device id.
- Use screenshots and `uiautomator dump` before blind tap loops.
- Treat account creation, wallet secrets, passwords, recovery phrases, and verification steps as human-handled boundaries.
- Use direct package launch when Play Store button behavior is unreliable.
- Log durable process learnings into workspace docs or memory after useful discoveries.

## Default workflow

1. Locate a working ADB binary.
2. Detect the active BlueStacks endpoint.
3. Connect and verify `adb devices` shows a usable target.
4. Open app directly by package when known.
5. If package is unknown, use Play Store search or details intent.
6. Dump UI hierarchy before precise taps.
7. Use screenshots/UI dumps to confirm progress after meaningful steps.
8. Fall back to direct package launch after install.

## ADB priority order

Prefer these binaries in order:

1. Android SDK platform-tools `adb.exe`
2. BlueStacks bundled `HD-Adb.exe`

Use whichever produces the most stable connection for the current session.

## BlueStacks endpoint recovery

When BlueStacks has restarted or `emulator-5554` is gone:

- probe local ports in the emulator range instead of assuming `5555`
- connect to the live endpoint (for example `127.0.0.1:5556`)
- verify with `adb devices`
- only then issue app commands

If the device shows `offline`, wait briefly and reconnect instead of spamming commands.

## Reliable actions

### Connect

- verify adb binary
- detect open local emulator port
- `adb connect <host:port>`
- `adb devices`

### Launch app

Preferred:
- `adb shell monkey -p <package> 1`

Alternative:
- `adb shell am start ...`

### Install / Play Store search

Use intents first:
- `market://search?q=<query>&c=apps`
- `market://details?id=<package>`

Then inspect UI and tap precise controls only after verification.

### Screen inspection

Use both when needed:
- screenshot capture for human verification
- `uiautomator dump` for control parsing

### UI-driven tap flow

Before taps:
- inspect current package/screen
- confirm target bounds or visible labels
- avoid repeated blind taps in webviews

## Known limitations

- Google account flows and other webview-heavy forms can ignore ADB taps unpredictably.
- Dropdowns inside embedded webviews are less reliable than native controls.
- Sensitive flows may require the user to take over briefly.

## Safe boundaries

Do not:
- store passwords, seed phrases, or private keys
- paste secrets into files or chat logs
- fully automate identity verification or account recovery flows
- claim or fabricate identity for account creation

## Read next

For concrete connection, Play Store, UI dump, and fallback patterns, read `references/bluestacks-adb-playbook.md`.

For the generic mobile game workflow layer built on top of those primitives, read `references/mobile-game-learner.md`.
