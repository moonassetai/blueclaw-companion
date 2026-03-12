from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from .execution_mode import DesktopOptions, DesktopTarget, resolve_desktop_options, resolve_desktop_target

from .workflow_runner import ROOT_DIR


SCRIPTS_DIR = ROOT_DIR / "scripts"
USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
USER32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
USER32.EnumWindows.restype = wintypes.BOOL
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.IsWindowVisible.restype = wintypes.BOOL
USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
USER32.GetWindowTextLengthW.restype = ctypes.c_int
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowTextW.restype = ctypes.c_int
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.GetWindowThreadProcessId.restype = wintypes.DWORD
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
USER32.GetWindowRect.restype = wintypes.BOOL
USER32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
USER32.GetClientRect.restype = wintypes.BOOL
USER32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
USER32.ClientToScreen.restype = wintypes.BOOL
USER32.IsIconic.argtypes = [wintypes.HWND]
USER32.IsIconic.restype = wintypes.BOOL
USER32.GetForegroundWindow.argtypes = []
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.SetForegroundWindow.restype = wintypes.BOOL
USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.ShowWindow.restype = wintypes.BOOL
USER32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
USER32.SetCursorPos.restype = wintypes.BOOL
USER32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
USER32.GetCursorPos.restype = wintypes.BOOL
USER32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.ULONG]
USER32.mouse_event.restype = None
KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL32.OpenProcess.restype = wintypes.HANDLE
KERNEL32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
KERNEL32.QueryFullProcessImageNameW.restype = wintypes.BOOL
KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL32.CloseHandle.restype = wintypes.BOOL


@dataclass(frozen=True)
class WindowMetadata:
    handle: int
    process_id: int
    process_name: str
    title: str
    window_left: int
    window_top: int
    window_width: int
    window_height: int
    client_left: int
    client_top: int
    client_width: int
    client_height: int
    is_minimized: bool
    is_foreground: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class WindowCapture:
    output_path: str
    capture_mode: str
    window: WindowMetadata | None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.window:
            payload["window"] = self.window.to_dict()
        return payload


def _get_window_text(hwnd: int) -> str:
    length = USER32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    USER32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _get_process_name(process_id: int) -> str:
    handle = KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return ""
    try:
        buffer_size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(buffer_size.value)
        if not KERNEL32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(buffer_size)):
            return ""
        return Path(buffer.value).stem
    finally:
        KERNEL32.CloseHandle(handle)


def _hwnd_to_int(hwnd: object) -> int:
    if isinstance(hwnd, int):
        return int(hwnd)
    try:
        return int(hwnd)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = ctypes.cast(hwnd, ctypes.c_void_p).value  # type: ignore[arg-type]
        return int(value or 0)


def _build_window_metadata(hwnd: int) -> WindowMetadata:
    process_id = wintypes.DWORD()
    USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

    window_rect = RECT()
    if not USER32.GetWindowRect(hwnd, ctypes.byref(window_rect)):
        raise OSError("Unable to read BlueStacks window bounds.")

    client_rect = RECT()
    has_client_rect = bool(USER32.GetClientRect(hwnd, ctypes.byref(client_rect)))
    client_origin = POINT(0, 0)
    has_client_origin = has_client_rect and bool(USER32.ClientToScreen(hwnd, ctypes.byref(client_origin)))

    client_width = max(0, client_rect.right - client_rect.left) if has_client_rect else max(0, window_rect.right - window_rect.left)
    client_height = max(0, client_rect.bottom - client_rect.top) if has_client_rect else max(0, window_rect.bottom - window_rect.top)
    window_width = max(0, window_rect.right - window_rect.left)
    window_height = max(0, window_rect.bottom - window_rect.top)
    foreground = USER32.GetForegroundWindow()

    return WindowMetadata(
        handle=int(hwnd),
        process_id=int(process_id.value),
        process_name=_get_process_name(int(process_id.value)),
        title=_get_window_text(hwnd),
        window_left=int(window_rect.left),
        window_top=int(window_rect.top),
        window_width=int(window_width),
        window_height=int(window_height),
        client_left=int(client_origin.x if has_client_origin else window_rect.left),
        client_top=int(client_origin.y if has_client_origin else window_rect.top),
        client_width=int(client_width),
        client_height=int(client_height),
        is_minimized=bool(USER32.IsIconic(hwnd)),
        is_foreground=_hwnd_to_int(foreground) == _hwnd_to_int(hwnd),
    )


def _enum_windows() -> list[WindowMetadata]:
    windows: list[WindowMetadata] = []

    @EnumWindowsProc
    def callback(hwnd: int, _lparam: int) -> bool:
        if not USER32.IsWindowVisible(hwnd):
            return True
        title = _get_window_text(hwnd)
        if not title.strip():
            return True
        try:
            windows.append(_build_window_metadata(hwnd))
        except OSError:
            pass
        return True

    USER32.EnumWindows(callback, 0)
    return windows


def _pick_best_window(windows: list[WindowMetadata]) -> WindowMetadata | None:
    if not windows:
        return None
    windows.sort(
        key=lambda item: (
            not item.is_foreground,
            item.is_minimized,
            -(item.client_width * item.client_height),
            item.process_id,
        )
    )
    return windows[0]


def _matches_bluestacks_hints(window: WindowMetadata) -> bool:
    process_hints = {"hd-player", "bluestacks", "bluestacksappplayer", "bluestacks_nxt"}
    title_hints = ("bluestacks", "app player")
    process_name = window.process_name.lower()
    title = window.title.lower()
    return process_name in process_hints or any(hint in title for hint in title_hints)


def detect_bluestacks_window(target: DesktopTarget | None = None) -> WindowMetadata | None:
    resolved_target = target or resolve_desktop_target()
    windows = _enum_windows()

    if resolved_target.window_handle is not None:
        exact = [window for window in windows if window.handle == int(resolved_target.window_handle)]
        return _pick_best_window(exact)

    if resolved_target.window_title_contains:
        title_hint = resolved_target.window_title_contains.lower()
        title_candidates = [window for window in windows if title_hint in window.title.lower()]
        return _pick_best_window(title_candidates)

    candidates = [window for window in windows if _matches_bluestacks_hints(window)]
    return _pick_best_window(candidates)


def get_window_geometry(window: WindowMetadata) -> dict[str, int]:
    return {
        "window_left": int(window.window_left),
        "window_top": int(window.window_top),
        "window_width": int(window.window_width),
        "window_height": int(window.window_height),
        "client_left": int(window.client_left),
        "client_top": int(window.client_top),
        "client_width": int(window.client_width),
        "client_height": int(window.client_height),
    }


def validate_window_geometry(window: WindowMetadata, options: DesktopOptions | None = None) -> WindowMetadata:
    resolved_options = options or resolve_desktop_options()
    errors: list[str] = []
    if resolved_options.expected_client_width is not None and window.client_width != resolved_options.expected_client_width:
        errors.append(
            f"expected client width {resolved_options.expected_client_width}, got {window.client_width}"
        )
    if resolved_options.expected_client_height is not None and window.client_height != resolved_options.expected_client_height:
        errors.append(
            f"expected client height {resolved_options.expected_client_height}, got {window.client_height}"
        )
    if errors:
        raise RuntimeError("BlueStacks client geometry mismatch: " + "; ".join(errors))
    return window


def focus_bluestacks_window(
    target: DesktopTarget | None = None,
    options: DesktopOptions | None = None,
) -> WindowMetadata:
    resolved_target = target or resolve_desktop_target()
    resolved_options = options or resolve_desktop_options()

    window = detect_bluestacks_window(target=resolved_target)
    if not window:
        raise RuntimeError("No BlueStacks window with a visible main handle was found.")

    hwnd = wintypes.HWND(window.handle)
    if window.is_minimized:
        USER32.ShowWindow(hwnd, SW_RESTORE)
    hwnd_value = _hwnd_to_int(hwnd)

    if window.is_foreground:
        return validate_window_geometry(_build_window_metadata(hwnd_value), resolved_options)

    attempts = max(1, int(resolved_options.focus_retries))
    delay_seconds = max(0, int(resolved_options.focus_retry_delay_ms)) / 1000.0
    for _ in range(attempts):
        USER32.SetForegroundWindow(hwnd)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        refreshed = _build_window_metadata(hwnd_value)
        if refreshed.is_foreground:
            return validate_window_geometry(refreshed, resolved_options)

    final_window = _build_window_metadata(hwnd_value)
    if final_window.is_foreground:
        return validate_window_geometry(final_window, resolved_options)
    raise RuntimeError(
        "BlueStacks window was found, but Windows rejected the focus request after "
        f"{attempts} attempt(s)."
    )


def click_bluestacks_relative(
    x: int,
    y: int,
    *,
    repeat_count: int = 1,
    delay_ms: int = 120,
    target: DesktopTarget | None = None,
    options: DesktopOptions | None = None,
) -> dict[str, Any]:
    if x < 0 or y < 0:
        raise ValueError("Relative click coordinates must be non-negative.")
    if repeat_count < 1 or repeat_count > 50:
        raise ValueError("repeat_count must be between 1 and 50.")
    if delay_ms < 0 or delay_ms > 60000:
        raise ValueError("delay_ms must be between 0 and 60000.")

    window = focus_bluestacks_window(target=target, options=options)
    if x >= window.client_width or y >= window.client_height:
        raise ValueError(
            f"Relative click ({x}, {y}) is outside client bounds {window.client_width}x{window.client_height}."
        )
    screen_x = window.client_left + int(x)
    screen_y = window.client_top + int(y)

    original = POINT()
    USER32.GetCursorPos(ctypes.byref(original))
    for index in range(int(repeat_count)):
        USER32.SetCursorPos(screen_x, screen_y)
        USER32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        USER32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        if index + 1 < int(repeat_count) and delay_ms > 0:
            time.sleep(int(delay_ms) / 1000.0)
    USER32.SetCursorPos(int(original.x), int(original.y))

    return {
        "relative_x": int(x),
        "relative_y": int(y),
        "screen_x": int(screen_x),
        "screen_y": int(screen_y),
        "repeat_count": int(repeat_count),
        "delay_ms": int(delay_ms),
        "window": window.to_dict(),
    }


def send_bluestacks_key(
    key: str,
    *,
    repeat_count: int = 1,
    delay_ms: int = 120,
    target: DesktopTarget | None = None,
    options: DesktopOptions | None = None,
) -> dict[str, Any]:
    if not key:
        raise ValueError("A non-empty key is required.")
    if repeat_count < 1 or repeat_count > 100:
        raise ValueError("repeat_count must be between 1 and 100.")
    if delay_ms < 0 or delay_ms > 60000:
        raise ValueError("delay_ms must be between 0 and 60000.")

    window = focus_bluestacks_window(target=target, options=options)
    escaped_key = key.replace("'", "''")
    send_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"1..{int(repeat_count)} | ForEach-Object {{ "
        f"[System.Windows.Forms.SendKeys]::SendWait('{escaped_key}'); "
        f"Start-Sleep -Milliseconds {int(delay_ms)} }}"
    )
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        send_script,
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT_DIR)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"Unable to send key to BlueStacks: {detail}")
    return {
        "key": key,
        "repeat_count": int(repeat_count),
        "delay_ms": int(delay_ms),
        "window": window.to_dict(),
    }


def _build_command(script_name: str, params: dict[str, Any]) -> list[str]:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                command.append(f"-{key}")
            continue
        command.extend([f"-{key}", str(value)])
    return command


def _run_json_script(script_name: str, params: dict[str, Any]) -> dict[str, Any]:
    command = _build_command(script_name, {"Json": True, **params})
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT_DIR)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{script_name} failed: {detail}")
    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError(f"{script_name} returned no output.")
    return json.loads(stdout)


def _parse_window(payload: dict[str, Any] | None) -> WindowMetadata | None:
    if not payload:
        return None
    return WindowMetadata(
        handle=int(payload["handle"]),
        process_id=int(payload["process_id"]),
        process_name=str(payload["process_name"]),
        title=str(payload["title"]),
        window_left=int(payload["window_left"]),
        window_top=int(payload["window_top"]),
        window_width=int(payload["window_width"]),
        window_height=int(payload["window_height"]),
        client_left=int(payload["client_left"]),
        client_top=int(payload["client_top"]),
        client_width=int(payload["client_width"]),
        client_height=int(payload["client_height"]),
        is_minimized=bool(payload["is_minimized"]),
        is_foreground=bool(payload["is_foreground"]),
    )


def capture_bluestacks_window(
    output_path: str | Path,
    *,
    full_screen_fallback: bool | None = None,
    target: DesktopTarget | None = None,
    options: DesktopOptions | None = None,
) -> WindowCapture:
    resolved_target = target or resolve_desktop_target()
    resolved_options = options or resolve_desktop_options()
    fallback = (
        bool(full_screen_fallback)
        if full_screen_fallback is not None
        else bool(resolved_options.fullscreen_fallback)
    )
    payload = _run_json_script(
        "capture-window.ps1",
        {
            "OutputPath": str(Path(output_path)),
            "FullScreenFallback": fallback,
            "WindowHandle": resolved_target.window_handle,
            "WindowTitleContains": resolved_target.window_title_contains,
            "ExpectedClientWidth": resolved_options.expected_client_width,
            "ExpectedClientHeight": resolved_options.expected_client_height,
        },
    )
    return WindowCapture(
        output_path=str(Path(payload["output_path"]).resolve()),
        capture_mode=str(payload["capture_mode"]),
        window=_parse_window(payload.get("window")),
    )


def to_jsonable(window: WindowMetadata | None) -> dict[str, object] | None:
    return window.to_dict() if window else None
