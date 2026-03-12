from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import shutil

from .execution_mode import ExecutionMode


class PerceptionBackend(str, Enum):
    ADB_UI_DUMP = "adb_ui_dump"
    DESKTOP_CAPTURE = "desktop_capture"


class OcrBackend(str, Enum):
    NONE = "none"
    TESSERACT = "ocr_tesseract"


class VisionBackend(str, Enum):
    NONE = "none"
    VISION_MODEL = "vision_model"


@dataclass(frozen=True)
class PerceptionPlan:
    execution_mode: str
    capture_backend: str
    ocr_backend: str
    vision_backend: str
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def resolve_perception_plan(
    *,
    execution_mode: str,
    prefer_ocr: bool = False,
    prefer_vision_model: bool = False,
) -> PerceptionPlan:
    mode = ExecutionMode.from_value(execution_mode)
    notes: list[str] = []

    if mode == ExecutionMode.DESKTOP:
        capture_backend = PerceptionBackend.DESKTOP_CAPTURE
    elif mode == ExecutionMode.ADB:
        capture_backend = PerceptionBackend.ADB_UI_DUMP
    else:
        capture_backend = PerceptionBackend.ADB_UI_DUMP
        notes.append("Hybrid mode is reserved for future use; using adb_ui_dump capture for now.")

    if prefer_ocr:
        if shutil.which("tesseract"):
            ocr_backend = OcrBackend.TESSERACT
            notes.append("OCR enabled via tesseract.")
        else:
            ocr_backend = OcrBackend.NONE
            notes.append("OCR requested but tesseract is not installed; continuing without OCR.")
    else:
        ocr_backend = OcrBackend.NONE

    if prefer_vision_model:
        vision_backend = VisionBackend.VISION_MODEL
        notes.append("vision_model backend is a placeholder hook and is not active yet.")
    else:
        vision_backend = VisionBackend.NONE

    return PerceptionPlan(
        execution_mode=mode.value,
        capture_backend=capture_backend.value,
        ocr_backend=ocr_backend.value,
        vision_backend=vision_backend.value,
        notes=notes,
    )
