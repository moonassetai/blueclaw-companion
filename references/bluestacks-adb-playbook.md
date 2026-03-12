# BlueStacks ADB Playbook

## Proven local paths

Common working binaries:

- `C:\Users\문명철\AppData\Local\Android\Sdk\platform-tools\adb.exe`
- `C:\Program Files\BlueStacks_nxt\HD-Adb.exe`
- `C:\Program Files\BlueStacks_nxt\HD-Player.exe`

## Port recovery pattern

Do not assume `127.0.0.1:5555` forever.

Observed behavior:
- after restart, BlueStacks may expose a different port such as `127.0.0.1:5556`
- old device ids can become invalid or offline

Recommended recovery:

1. Probe likely local ports.
2. Find an open emulator endpoint.
3. `adb connect <endpoint>`
4. Verify target in `adb devices`

## MapleStory Idle learnings

Observed package:
- `com.nexon.ma`

Reliable sequence:
1. Search Play Store with intent or open details page.
2. Use `uiautomator dump` to confirm result cards or install button.
3. Tap install only after verifying the visible target.
4. If Play Store launch button is unreliable, launch directly with package name.
5. Verify foreground package with `dumpsys window windows`.

## Play Store patterns

### Search

`market://search?q=<query>&c=apps`

### Direct app page

`market://details?id=<package>`

### Good fallback

If install succeeded but the store UI is awkward:
- query installed packages
- launch directly by package

## UI dump pattern

Use `uiautomator dump` and pull the XML locally.
Then search for:
- visible labels
- button text
- content descriptions
- bounds

This is often more reliable than screenshot-only reasoning.

## Webview warning

Google signup and similar embedded flows can be partially native and partially web-rendered.

Implications:
- text fields may work
- dropdowns may fail via simple taps
- some actions may require a brief human assist

## MULTIVAC design implications

Blueclaw Companion should eventually expose these reusable operations:

- detectBlueStacksEndpoint()
- connectBlueStacks()
- launchPackage(packageName)
- openPlayStoreSearch(query)
- openPlayStoreDetails(packageName)
- captureScreenshot(outputPath)
- dumpUi(outputPath)
- findVisibleText(pattern)
- tap(x, y)
- inputText(text)
- verifyForegroundPackage()

## Approval boundaries

Require human confirmation for:
- passwords
- account creation identity details
- recovery phrases
- wallet secrets
- phone/email verification

Allow automation for:
- app install/open
- repetitive navigation
- screenshots
- UI inspection
- low-risk tap flows
