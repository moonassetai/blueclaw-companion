from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import shutil

from .execution_mode import ExecutionMode


class ControlBackend(str, Enum):
    ADB = "adb"
    DESKTOP = "desktop"
    SCRCPY = "scrcpy"


@dataclass(frozen=True)
class ControlPlan:
    execution_mode: str
    control_backend: str
    scrcpy_available: bool
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def resolve_control_plan(
    *,
    control_mode: str,
    prefer_scrcpy: bool = False,
) -> ControlPlan:
    mode = ExecutionMode.from_value(control_mode)
    notes: list[str] = []
    scrcpy_available = bool(shutil.which("scrcpy"))

    if mode == ExecutionMode.DESKTOP:
        backend = ControlBackend.DESKTOP
    elif mode == ExecutionMode.ADB:
        backend = ControlBackend.ADB
    else:
        backend = ControlBackend.ADB
        notes.append("Hybrid mode is reserved for future use; using adb control for now.")

    if prefer_scrcpy:
        if scrcpy_available:
            notes.append("scrcpy is available and can be integrated as a future control backend.")
        else:
            notes.append("scrcpy preference requested but executable is not available on PATH.")

    return ControlPlan(
        execution_mode=mode.value,
        control_backend=backend.value,
        scrcpy_available=scrcpy_available,
        notes=notes,
    )
