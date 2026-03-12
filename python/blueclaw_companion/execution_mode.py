from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import os
from typing import Mapping


class ExecutionMode(str, Enum):
    ADB = "adb"
    DESKTOP = "desktop"
    HYBRID = "hybrid"

    @classmethod
    def from_value(cls, value: str) -> "ExecutionMode":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            allowed = ", ".join(mode.value for mode in cls)
            raise ValueError(f"Unsupported execution mode `{value}`. Allowed values: {allowed}") from exc


@dataclass(frozen=True)
class DesktopTarget:
    window_handle: int | None = None
    window_title_contains: str | None = None

    def is_explicit(self) -> bool:
        return self.window_handle is not None or bool(self.window_title_contains)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DesktopOptions:
    fullscreen_fallback: bool = True
    expected_client_width: int | None = None
    expected_client_height: int | None = None
    focus_retries: int = 3
    focus_retry_delay_ms: int = 120

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def resolve_desktop_target(
    *,
    window_handle: int | None = None,
    window_title_contains: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> DesktopTarget:
    env = environ or os.environ
    resolved_handle = window_handle if window_handle is not None else _parse_int(env.get("BLUECLAW_WINDOW_HANDLE"))

    resolved_title = window_title_contains
    if resolved_title is None:
        env_title = env.get("BLUECLAW_WINDOW_TITLE_CONTAINS")
        resolved_title = env_title.strip() if env_title and env_title.strip() else None
    elif not resolved_title.strip():
        resolved_title = None

    return DesktopTarget(
        window_handle=resolved_handle,
        window_title_contains=resolved_title,
    )


def resolve_desktop_options(
    *,
    fullscreen_fallback: bool | None = None,
    expected_client_width: int | None = None,
    expected_client_height: int | None = None,
    focus_retries: int | None = None,
    focus_retry_delay_ms: int | None = None,
    environ: Mapping[str, str] | None = None,
) -> DesktopOptions:
    env = environ or os.environ
    env_fullscreen = _parse_bool(env.get("BLUECLAW_DESKTOP_FULLSCREEN_FALLBACK"))
    resolved_fullscreen = fullscreen_fallback if fullscreen_fallback is not None else env_fullscreen
    if resolved_fullscreen is None:
        resolved_fullscreen = True

    resolved_expected_width = (
        expected_client_width
        if expected_client_width is not None
        else _parse_int(env.get("BLUECLAW_EXPECTED_CLIENT_WIDTH"))
    )
    resolved_expected_height = (
        expected_client_height
        if expected_client_height is not None
        else _parse_int(env.get("BLUECLAW_EXPECTED_CLIENT_HEIGHT"))
    )
    resolved_focus_retries = focus_retries if focus_retries is not None else _parse_int(env.get("BLUECLAW_FOCUS_RETRIES"))
    resolved_focus_delay = (
        focus_retry_delay_ms
        if focus_retry_delay_ms is not None
        else _parse_int(env.get("BLUECLAW_FOCUS_RETRY_DELAY_MS"))
    )

    return DesktopOptions(
        fullscreen_fallback=bool(resolved_fullscreen),
        expected_client_width=resolved_expected_width,
        expected_client_height=resolved_expected_height,
        focus_retries=max(1, int(resolved_focus_retries if resolved_focus_retries is not None else 3)),
        focus_retry_delay_ms=max(0, int(resolved_focus_delay if resolved_focus_delay is not None else 120)),
    )
