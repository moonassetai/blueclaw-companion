from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .control_backends import resolve_control_plan
from .execution_mode import DesktopTarget
from .perception_backends import resolve_perception_plan


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"


@dataclass(frozen=True)
class ShortcutCapability:
    name: str
    category: str
    available: bool
    status: str
    readiness: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _script_exists(name: str) -> bool:
    return (SCRIPTS_DIR / name).exists()


def _resolve_adb_executable(adb_path: str | None = None) -> str | None:
    if adb_path:
        candidate = Path(adb_path)
        if candidate.exists():
            return str(candidate)
    return shutil.which("adb")


def _probe_adb_device_reachability(*, adb_path: str | None = None, device: str | None = None) -> dict[str, object]:
    adb_executable = _resolve_adb_executable(adb_path)
    if not adb_executable:
        return {
            "adb_binary_found": False,
            "adb_device_reachable": False,
            "adb_selected_device": device,
            "adb_connected_devices": [],
            "adb_error": "adb executable not found on PATH.",
        }
    try:
        result = subprocess.run(
            [adb_executable, "devices"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=ROOT_DIR,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "adb_binary_found": True,
            "adb_device_reachable": False,
            "adb_selected_device": device,
            "adb_connected_devices": [],
            "adb_error": str(exc).strip() or "Failed to execute adb devices.",
        }

    stdout = result.stdout.strip()
    lines = [line.strip() for line in stdout.splitlines()]
    device_lines = [line for line in lines[1:] if line]
    connected_devices: list[str] = []
    reachable = False
    for line in device_lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, status = parts[0], parts[1].lower()
        if status == "device":
            connected_devices.append(serial)
    if device:
        reachable = device in connected_devices
    else:
        reachable = len(connected_devices) > 0

    return {
        "adb_binary_found": True,
        "adb_device_reachable": reachable,
        "adb_selected_device": device,
        "adb_connected_devices": connected_devices,
        "adb_error": None if reachable else "No reachable adb device reported by `adb devices`.",
    }


def _probe_bluestacks_window(target: DesktopTarget | None = None) -> dict[str, object]:
    if os.name != "nt":
        return {
            "bluestacks_window_found": False,
            "bluestacks_window_handle": None,
            "bluestacks_window_title": None,
            "bluestacks_window_error": "Desktop window probing is supported only on Windows.",
        }
    try:
        from .window_control import detect_bluestacks_window

        window = detect_bluestacks_window(target=target)
        if window:
            return {
                "bluestacks_window_found": True,
                "bluestacks_window_handle": int(window.handle),
                "bluestacks_window_title": window.title,
                "bluestacks_window_error": None,
            }
        return {
            "bluestacks_window_found": False,
            "bluestacks_window_handle": None,
            "bluestacks_window_title": None,
            "bluestacks_window_error": "BlueStacks desktop window not found.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "bluestacks_window_found": False,
            "bluestacks_window_handle": None,
            "bluestacks_window_title": None,
            "bluestacks_window_error": str(exc).strip() or "BlueStacks window probe failed.",
        }


def _readiness_color(*, available: bool, required: bool = True) -> str:
    if available:
        return "green"
    return "red" if required else "yellow"


def list_shortcut_capabilities(
    *,
    use_ocr: bool = False,
    adb_path: str | None = None,
    device: str | None = None,
    desktop_target: DesktopTarget | None = None,
) -> list[ShortcutCapability]:
    adb_probe = _probe_adb_device_reachability(adb_path=adb_path, device=device)
    window_probe = _probe_bluestacks_window(target=desktop_target)
    is_windows = os.name == "nt"
    tesseract_available = bool(shutil.which("tesseract"))
    scrcpy_available = bool(shutil.which("scrcpy"))
    adb_binary_found = bool(adb_probe["adb_binary_found"])
    adb_device_reachable = bool(adb_probe["adb_device_reachable"])
    bluestacks_window_found = bool(window_probe["bluestacks_window_found"])

    ocr_required = bool(use_ocr)
    ocr_ready = tesseract_available if ocr_required else True
    ocr_status = "active" if tesseract_available else ("optional_missing" if ocr_required else "not_requested")

    return [
        ShortcutCapability(
            name="adb_ui_dump",
            category="perception",
            available=adb_binary_found and adb_device_reachable and _script_exists("capture-all.ps1"),
            status="active" if adb_binary_found else "unavailable",
            readiness=_readiness_color(available=adb_binary_found and adb_device_reachable and _script_exists("capture-all.ps1")),
            notes="Requires adb binary + reachable device + capture-all.ps1.",
        ),
        ShortcutCapability(
            name="desktop_capture",
            category="perception",
            available=is_windows and bluestacks_window_found and _script_exists("capture-window.ps1"),
            status="active" if is_windows else "unavailable",
            readiness=_readiness_color(available=is_windows and bluestacks_window_found and _script_exists("capture-window.ps1")),
            notes="Requires Windows + BlueStacks window + capture-window.ps1.",
        ),
        ShortcutCapability(
            name="ocr_tesseract",
            category="perception",
            available=ocr_ready,
            status=ocr_status,
            readiness=_readiness_color(available=ocr_ready, required=ocr_required),
            notes="OCR backend readiness. Required only when --use-ocr is enabled.",
        ),
        ShortcutCapability(
            name="vision_model",
            category="perception",
            available=False,
            status="placeholder",
            readiness="yellow",
            notes="Reserved for future model-based classification.",
        ),
        ShortcutCapability(
            name="adb_control",
            category="control",
            available=adb_binary_found and adb_device_reachable and _script_exists("tap.ps1"),
            status="active" if adb_binary_found else "unavailable",
            readiness=_readiness_color(available=adb_binary_found and adb_device_reachable and _script_exists("tap.ps1")),
            notes="Requires adb binary + reachable device + tap.ps1.",
        ),
        ShortcutCapability(
            name="desktop_control",
            category="control",
            available=is_windows and bluestacks_window_found,
            status="active" if is_windows else "unavailable",
            readiness=_readiness_color(available=is_windows and bluestacks_window_found),
            notes="Requires Windows + detected BlueStacks window.",
        ),
        ShortcutCapability(
            name="scrcpy",
            category="control",
            available=scrcpy_available,
            status="discoverable" if scrcpy_available else "placeholder",
            readiness=_readiness_color(available=scrcpy_available, required=False),
            notes="Optional accelerator for future low-latency stream/control.",
        ),
    ]


def build_shortcut_summary(
    *,
    execution_mode: str,
    use_ocr: bool = False,
    prefer_scrcpy: bool = False,
    prefer_vision_model: bool = False,
    adb_path: str | None = None,
    device: str | None = None,
    desktop_target: DesktopTarget | None = None,
) -> dict[str, Any]:
    perception = resolve_perception_plan(
        execution_mode=execution_mode,
        prefer_ocr=use_ocr,
        prefer_vision_model=prefer_vision_model,
    )
    control = resolve_control_plan(
        control_mode=execution_mode,
        prefer_scrcpy=prefer_scrcpy,
    )
    adb_probe = _probe_adb_device_reachability(adb_path=adb_path, device=device)
    window_probe = _probe_bluestacks_window(target=desktop_target)
    capabilities = list_shortcut_capabilities(
        use_ocr=use_ocr,
        adb_path=adb_path,
        device=device,
        desktop_target=desktop_target,
    )
    availability = {
        item.name: {
            "available": item.available,
            "status": item.status,
            "readiness": item.readiness,
        }
        for item in capabilities
    }
    runtime_checks = {
        **adb_probe,
        **window_probe,
        "ocr_requested": bool(use_ocr),
        "ocr_backend_ready": bool(shutil.which("tesseract")) if use_ocr else True,
    }
    return {
        "perception": perception.to_dict(),
        "control": control.to_dict(),
        "runtime_checks": runtime_checks,
        "capabilities": [capability.to_dict() for capability in capabilities],
        "availability": availability,
    }
