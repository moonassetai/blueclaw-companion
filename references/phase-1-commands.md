# Phase 1 Command Set

Blueclaw Companion Phase 1 is a lean PowerShell toolkit for driving BlueStacks over ADB on Windows.

## ADB resolution order

The scripts prefer:

1. Android SDK `platform-tools\adb.exe`
2. BlueStacks `HD-Adb.exe`

Override with `-AdbPath` on any script when needed.

## Device targeting

- If you pass `-Device 127.0.0.1:5556`, the scripts target that device directly.
- If you omit `-Device`, the scripts try an already-online adb device first.
- If no single online device is available, they probe common BlueStacks localhost ports and connect automatically.

## Commands

### Detect BlueStacks endpoint

```powershell
.\scripts\detect-bluestacks-endpoint.ps1
.\scripts\detect-bluestacks-endpoint.ps1 -Ports 5555,5556,5565
```

### Connect to BlueStacks

```powershell
.\scripts\connect-bluestacks.ps1
.\scripts\connect-bluestacks.ps1 -Device 127.0.0.1:5555
```

### Inspect the foreground app

```powershell
.\scripts\get-running-app.ps1
.\scripts\get-running-app.ps1 -Device 127.0.0.1:5555
```

### Open a Play Store search

```powershell
.\scripts\open-playstore-search.ps1 -Query "MapleStory Idle"
```

This uses the `market://search?q=<query>&c=apps` intent.

### Launch an installed app

```powershell
.\scripts\open-app.ps1 -Package com.nexon.ma
```

This uses `monkey` for direct package launch.

### Save a screenshot locally

```powershell
.\scripts\screenshot.ps1
.\scripts\screenshot.ps1 -OutputPath .\artifacts\multivac-home.png
```

### Dump the current UI hierarchy

```powershell
.\scripts\dump-ui.ps1
.\scripts\dump-ui.ps1 -OutputPath .\artifacts\multivac-home.xml
```

This runs `uiautomator dump` on the device, then pulls the XML locally.

### Tap a coordinate

```powershell
.\scripts\tap.ps1 -X 640 -Y 360
```

### Type text into the focused input

```powershell
.\scripts\type-text.ps1 -Text "hello world"
```

Spaces are converted for Android `input text`.

## Recommended Phase 1 flow

1. Run `connect-bluestacks.ps1`
2. Run `get-running-app.ps1`
3. Open the Play Store search or app package
4. Use `screenshot.ps1` and `dump-ui.ps1` before precise taps
5. Use `tap.ps1` and `type-text.ps1` only after confirming the visible target

## Boundaries

Do not use these scripts to store or automate wallet secrets, account passwords, recovery phrases, or identity verification details.
