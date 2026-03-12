from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .control_backends import resolve_control_plan
from .perception_backends import resolve_perception_plan


@dataclass(frozen=True)
class ShortcutCapability:
    name: str
    category: str
    available: bool
    status: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def list_shortcut_capabilities() -> list[ShortcutCapability]:
    perception = resolve_perception_plan(execution_mode="adb", prefer_ocr=True, prefer_vision_model=True)
    control = resolve_control_plan(control_mode="adb", prefer_scrcpy=True)
    ocr_available = perception.ocr_backend != "none"

    return [
        ShortcutCapability(
            name="adb_ui_dump",
            category="perception",
            available=True,
            status="active",
            notes="Default Android UI hierarchy capture path.",
        ),
        ShortcutCapability(
            name="desktop_capture",
            category="perception",
            available=True,
            status="active",
            notes="Window/fullscreen capture path for BlueStacks desktop mode.",
        ),
        ShortcutCapability(
            name="ocr_tesseract",
            category="perception",
            available=ocr_available,
            status="active" if ocr_available else "optional_missing",
            notes="Enabled automatically when requested and tesseract is installed.",
        ),
        ShortcutCapability(
            name="vision_model",
            category="perception",
            available=False,
            status="placeholder",
            notes="Hook reserved for future model-based screen classification.",
        ),
        ShortcutCapability(
            name="adb_control",
            category="control",
            available=True,
            status="active",
            notes="Default input backend for Android-side actions.",
        ),
        ShortcutCapability(
            name="desktop_control",
            category="control",
            available=True,
            status="active",
            notes="BlueStacks window focus/click/key path for desktop mode.",
        ),
        ShortcutCapability(
            name="scrcpy",
            category="control",
            available=control.scrcpy_available,
            status="discoverable" if control.scrcpy_available else "placeholder",
            notes="Planned accelerator for low-friction stream/control integration.",
        ),
    ]


def build_shortcut_summary(
    *,
    execution_mode: str,
    use_ocr: bool = False,
    prefer_scrcpy: bool = False,
    prefer_vision_model: bool = False,
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
    return {
        "perception": perception.to_dict(),
        "control": control.to_dict(),
        "capabilities": [capability.to_dict() for capability in list_shortcut_capabilities()],
    }
