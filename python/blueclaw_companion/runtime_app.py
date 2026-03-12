from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, TypeVar

from .desktop_state import capture_desktop_state
from .execution_mode import DesktopOptions, DesktopTarget, ExecutionMode
from .mobile_game_learner import capture_current_screen, run_learning_cycle
from .window_control import (
    WindowMetadata,
    click_bluestacks_relative,
    detect_bluestacks_window,
    focus_bluestacks_window,
    send_bluestacks_key,
)
from .workflow_runner import ROOT_DIR, WorkflowError, run_workflow


SCRIPTS_DIR = ROOT_DIR / "scripts"
T = TypeVar("T")


@dataclass(frozen=True)
class RuntimeStatus:
    selected_mode: str
    effective_mode: str
    target: dict[str, object]
    bluestacks_found: bool
    adb_connected: bool
    adb_message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _short_error(message: str) -> str:
    if not message:
        return "Unknown error."
    line = message.strip().splitlines()[0].strip()
    if not line:
        return "Unknown error."
    return line


def _window_payload(window: WindowMetadata | None) -> dict[str, object] | None:
    return window.to_dict() if window else None


def _pin_desktop_target(desktop_target: DesktopTarget) -> tuple[DesktopTarget, WindowMetadata | None]:
    window = detect_bluestacks_window(target=desktop_target)
    if not window:
        return desktop_target, None
    if desktop_target.window_handle == window.handle:
        return desktop_target, window
    return (
        DesktopTarget(
            window_handle=window.handle,
            window_title_contains=desktop_target.window_title_contains,
        ),
        window,
    )


def _run_script(script_name: str, params: dict[str, Any] | None = None) -> subprocess.CompletedProcess[str]:
    script_path = SCRIPTS_DIR / script_name
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    for key, value in (params or {}).items():
        if value is None or value == "":
            continue
        command.extend([f"-{key}", str(value)])
    return subprocess.run(command, capture_output=True, text=True, cwd=ROOT_DIR)


def try_connect_adb(*, device: str | None = None, adb_path: str | None = None) -> tuple[bool, str]:
    result = _run_script(
        "connect-bluestacks.ps1",
        {
            "Device": device,
            "AdbPath": adb_path,
        },
    )
    if result.returncode == 0:
        stdout = result.stdout.strip()
        return True, stdout or "ADB connected."
    detail = result.stderr.strip() or result.stdout.strip() or f"connect-bluestacks.ps1 failed with exit code {result.returncode}"
    return False, _short_error(detail)


def resolve_effective_mode(
    selected_mode: ExecutionMode,
    *,
    bluestacks_found: bool,
) -> ExecutionMode:
    if selected_mode == ExecutionMode.HYBRID:
        return ExecutionMode.DESKTOP if bluestacks_found else ExecutionMode.ADB
    return selected_mode


def _run_with_mode_fallback(
    *,
    selected_mode: ExecutionMode,
    desktop_available: bool,
    connect_adb: bool,
    command_label: str,
    run_desktop: Callable[[], T],
    run_adb: Callable[[], T],
    connect_adb_fn: Callable[[], tuple[bool, str]],
) -> tuple[T, ExecutionMode, bool, str, dict[str, str] | None]:
    adb_connected = False
    adb_message = "not_attempted"
    fallback: dict[str, str] | None = None

    if selected_mode == ExecutionMode.DESKTOP:
        try:
            return run_desktop(), ExecutionMode.DESKTOP, adb_connected, adb_message, fallback
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{command_label} failed: {_short_error(str(exc))}") from exc

    if selected_mode == ExecutionMode.ADB:
        if connect_adb:
            adb_connected, adb_message = connect_adb_fn()
        try:
            return run_adb(), ExecutionMode.ADB, adb_connected, adb_message, fallback
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{command_label} failed: {_short_error(str(exc))}") from exc

    if desktop_available:
        try:
            return run_desktop(), ExecutionMode.DESKTOP, adb_connected, adb_message, fallback
        except Exception as desktop_exc:  # noqa: BLE001
            fallback = {"desktop_error": _short_error(str(desktop_exc))}
    else:
        fallback = {"desktop_error": "BlueStacks desktop window was not found."}

    if connect_adb:
        adb_connected, adb_message = connect_adb_fn()
    try:
        return run_adb(), ExecutionMode.ADB, adb_connected, adb_message, fallback
    except Exception as adb_exc:  # noqa: BLE001
        desktop_error = (fallback or {}).get("desktop_error", "Desktop execution path failed.")
        adb_error = _short_error(str(adb_exc))
        raise RuntimeError(
            f"{command_label} failed in hybrid mode. Desktop error: {desktop_error}. ADB error: {adb_error}."
        ) from adb_exc


def inspect_runtime(
    *,
    mode: str,
    profile: str,
    use_ocr: bool,
    capture_screenshot: bool,
    connect_adb: bool,
    focus_window: bool,
    device: str | None,
    adb_path: str | None,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    runtime_target, window = _pin_desktop_target(desktop_target)
    bluestacks_found = window is not None

    focused_window = window
    focus_error = ""

    def _run_desktop() -> Any:
        nonlocal focused_window, bluestacks_found, focus_error
        if focus_window:
            try:
                focused_window = focus_bluestacks_window(target=runtime_target, options=desktop_options)
                bluestacks_found = True
            except Exception as exc:  # noqa: BLE001
                focus_error = _short_error(str(exc))
        return run_learning_cycle(
            profile_id=profile,
            capture=True,
            connect=False,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=ExecutionMode.DESKTOP.value,
            desktop_target=runtime_target,
            desktop_options=desktop_options,
            execute_safe_actions=False,
        )

    def _run_adb() -> Any:
        return run_learning_cycle(
            profile_id=profile,
            capture=True,
            connect=False,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=ExecutionMode.ADB.value,
            desktop_target=runtime_target,
            desktop_options=desktop_options,
            execute_safe_actions=False,
        )

    learner_result, effective_mode, adb_connected, adb_message, fallback_detail = _run_with_mode_fallback(
        selected_mode=selected_mode,
        desktop_available=bluestacks_found,
        connect_adb=connect_adb,
        command_label="Inspect",
        run_desktop=_run_desktop,
        run_adb=_run_adb,
        connect_adb_fn=lambda: try_connect_adb(device=device, adb_path=adb_path),
    )

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=runtime_target.to_dict(),
        bluestacks_found=bluestacks_found,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )
    payload = {
        "command": "inspect",
        "status": status.to_dict(),
        "window": _window_payload(focused_window),
        "focus_error": focus_error or None,
        "screen": learner_result.screen,
        "state": learner_result.state,
        "action": learner_result.action,
        "decision": learner_result.decision,
        "memory_path": learner_result.memory_path,
        "fallback": fallback_detail,
    }
    return payload


def capture_runtime(
    *,
    mode: str,
    output_path: str | None,
    use_ocr: bool,
    connect_adb: bool,
    device: str | None,
    adb_path: str | None,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    runtime_target, window = _pin_desktop_target(desktop_target)

    def _run_desktop() -> dict[str, Any]:
        screenshot = output_path or str(ROOT_DIR / "artifacts" / f"runtime-capture-{time.strftime('%Y%m%d-%H%M%S')}.png")
        result = capture_desktop_state(
            screenshot_path=screenshot,
            use_ocr=use_ocr,
            desktop_target=runtime_target,
            desktop_options=desktop_options,
        )
        return {
            "analysis": result.analysis.to_dict(),
            "capture": result.capture.to_dict(),
        }

    def _run_adb() -> dict[str, Any]:
        analysis = capture_current_screen(
            connect=False,
            capture_screenshot=True,
            use_ocr=use_ocr,
            control_mode=ExecutionMode.ADB.value,
            desktop_target=runtime_target,
            desktop_options=desktop_options,
        ).to_dict()
        return {
            "analysis": analysis,
            "capture": {
                "output_path": analysis.get("screenshot_path"),
                "capture_mode": "adb_screenshot",
                "window": None,
            },
        }

    runtime_result, effective_mode, adb_connected, adb_message, fallback_detail = _run_with_mode_fallback(
        selected_mode=selected_mode,
        desktop_available=window is not None,
        connect_adb=connect_adb,
        command_label="Capture",
        run_desktop=_run_desktop,
        run_adb=_run_adb,
        connect_adb_fn=lambda: try_connect_adb(device=device, adb_path=adb_path),
    )

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=runtime_target.to_dict(),
        bluestacks_found=window is not None,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )
    return {
        "command": "capture",
        "status": status.to_dict(),
        "capture": runtime_result["capture"],
        "analysis": runtime_result["analysis"],
        "fallback": fallback_detail,
    }


def focus_runtime(*, desktop_target: DesktopTarget, desktop_options: DesktopOptions) -> dict[str, object]:
    runtime_target, _window = _pin_desktop_target(desktop_target)
    try:
        window = focus_bluestacks_window(target=runtime_target, options=desktop_options)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Focus failed: {_short_error(str(exc))}") from exc
    return {
        "command": "focus",
        "target": runtime_target.to_dict(),
        "window": window.to_dict(),
    }


def send_key_runtime(
    *,
    key: str,
    repeat_count: int,
    delay_ms: int,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    runtime_target, _window = _pin_desktop_target(desktop_target)
    try:
        payload = send_bluestacks_key(
            key,
            repeat_count=repeat_count,
            delay_ms=delay_ms,
            target=runtime_target,
            options=desktop_options,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Send-key failed: {_short_error(str(exc))}") from exc
    return {
        "command": "send-key",
        "target": runtime_target.to_dict(),
        "result": payload,
    }


def click_runtime(
    *,
    x: int,
    y: int,
    repeat_count: int,
    delay_ms: int,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    runtime_target, _window = _pin_desktop_target(desktop_target)
    try:
        payload = click_bluestacks_relative(
            x,
            y,
            repeat_count=repeat_count,
            delay_ms=delay_ms,
            target=runtime_target,
            options=desktop_options,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Click failed: {_short_error(str(exc))}") from exc
    return {
        "command": "click",
        "target": runtime_target.to_dict(),
        "result": payload,
    }


def connect_runtime(*, device: str | None, adb_path: str | None) -> dict[str, object]:
    connected, message = try_connect_adb(device=device, adb_path=adb_path)
    return {
        "command": "connect",
        "adb_connected": connected,
        "message": message,
    }


def learner_runtime(
    *,
    mode: str,
    profile: str,
    use_ocr: bool,
    capture_screenshot: bool,
    connect_adb: bool,
    device: str | None,
    adb_path: str | None,
    execute_safe_actions: bool,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    runtime_target, window = _pin_desktop_target(desktop_target)
    result, effective_mode, adb_connected, adb_message, fallback_detail = _run_with_mode_fallback(
        selected_mode=selected_mode,
        desktop_available=window is not None,
        connect_adb=connect_adb,
        command_label="Learner",
        run_desktop=lambda: run_learning_cycle(
            profile_id=profile,
            capture=True,
            connect=False,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=ExecutionMode.DESKTOP.value,
            desktop_target=runtime_target,
            desktop_options=desktop_options,
            execute_safe_actions=execute_safe_actions,
        ),
        run_adb=lambda: run_learning_cycle(
            profile_id=profile,
            capture=True,
            connect=False,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=ExecutionMode.ADB.value,
            desktop_target=runtime_target,
            desktop_options=desktop_options,
            execute_safe_actions=execute_safe_actions,
        ),
        connect_adb_fn=lambda: try_connect_adb(device=device, adb_path=adb_path),
    )

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=runtime_target.to_dict(),
        bluestacks_found=window is not None,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )
    return {
        "command": "learner",
        "status": status.to_dict(),
        "result": result.to_dict(),
        "fallback": fallback_detail,
    }


def workflow_runtime(
    *,
    mode: str,
    workflow_name: str,
    vars_items: list[str],
    connect_adb: bool,
    device: str | None,
    adb_path: str | None,
    dry_run: bool,
    approve_sensitive: bool,
    approve_all_boundaries: bool,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    runtime_target, window = _pin_desktop_target(desktop_target)

    variables: dict[str, str] = {}
    for item in vars_items:
        if "=" not in item:
            raise RuntimeError(f"Invalid --var value `{item}`. Expected KEY=VALUE.")
        key, value = item.split("=", 1)
        variables[key] = value

    def _run_workflow(execution_mode: ExecutionMode) -> Any:
        try:
            return run_workflow(
                workflow_name=workflow_name,
                variable_overrides=variables,
                dry_run=dry_run,
                approve_sensitive=approve_sensitive,
                approve_all_boundaries=approve_all_boundaries,
                execution_mode=execution_mode.value,
                desktop_target=runtime_target,
                desktop_options=desktop_options,
            )
        except WorkflowError as exc:
            raise RuntimeError(_short_error(str(exc))) from exc

    result, effective_mode, adb_connected, adb_message, fallback_detail = _run_with_mode_fallback(
        selected_mode=selected_mode,
        desktop_available=window is not None,
        connect_adb=connect_adb,
        command_label="Workflow",
        run_desktop=lambda: _run_workflow(ExecutionMode.DESKTOP),
        run_adb=lambda: _run_workflow(ExecutionMode.ADB),
        connect_adb_fn=lambda: try_connect_adb(device=device, adb_path=adb_path),
    )

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=runtime_target.to_dict(),
        bluestacks_found=window is not None,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )

    return {
        "command": "workflow",
        "status": status.to_dict(),
        "result": result.to_dict(),
        "fallback": fallback_detail,
    }


def render_runtime_result(payload: dict[str, object]) -> str:
    command = str(payload.get("command", "run"))
    if command == "inspect":
        status = payload["status"]
        state = payload["state"]
        action = payload["action"]
        lines = [
            f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
            f"BlueStacks found: {status['bluestacks_found']}",
            f"ADB connected: {status['adb_connected']} ({status['adb_message']})",
            f"State: {state['state']} ({state['confidence']:.2f})",
            f"Suggested action: {action['action']} [{action['action_type']}]",
        ]
        if payload.get("focus_error"):
            lines.append(f"Focus warning: {payload['focus_error']}")
        return "\n".join(lines)

    if command == "capture":
        status = payload["status"]
        capture = payload["capture"]
        analysis = payload["analysis"]
        return "\n".join(
            [
                f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
                f"Capture mode: {capture['capture_mode']}",
                f"Output: {capture['output_path'] or 'n/a'}",
                f"State: {analysis['state']}",
                f"OCR: {analysis['ocr_status']}",
            ]
        )

    if command == "connect":
        return f"ADB connected: {payload['adb_connected']} ({payload['message']})"

    if command in {"focus", "send-key", "click"}:
        return json.dumps(payload, indent=2)

    if command == "learner":
        status = payload["status"]
        result = payload["result"]
        return "\n".join(
            [
                f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
                f"Detected state: {result['state']['state']}",
                f"Suggested action: {result['action']['action']}",
                f"Decision: {result['decision']['decision']}",
                f"Memory: {result['memory_path']}",
            ]
        )

    if command == "workflow":
        status = payload["status"]
        result = payload["result"]
        return "\n".join(
            [
                f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
                f"BlueStacks found: {status['bluestacks_found']}",
                f"ADB connected: {status['adb_connected']} ({status['adb_message']})",
                f"Workflow: {result['workflow']}",
                f"Status: {result['status']}",
                f"Message: {result['message']}",
            ]
        )

    return json.dumps(payload, indent=2)
