from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .execution_mode import DesktopOptions, DesktopTarget, resolve_desktop_options, resolve_desktop_target
from .screen_analysis import ScreenAnalysis, analyze_screen
from .window_control import WindowCapture, WindowMetadata, capture_bluestacks_window, get_window_geometry


@dataclass(frozen=True)
class DesktopVisualState:
    source: str
    screenshot_path: str
    capture_mode: str
    window: dict[str, object] | None
    geometry: dict[str, int] | None
    expected_geometry: dict[str, int] | None
    text_signals: list[str]
    ocr_status: str
    template_matching_ready: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DesktopCaptureResult:
    capture: WindowCapture
    analysis: ScreenAnalysis
    visual_state: DesktopVisualState

    def to_dict(self) -> dict[str, object]:
        return {
            "capture": self.capture.to_dict(),
            "analysis": self.analysis.to_dict(),
            "visual_state": self.visual_state.to_dict(),
        }


def _window_payload(window: WindowMetadata | None) -> dict[str, object] | None:
    return window.to_dict() if window else None


def capture_desktop_state(
    *,
    screenshot_path: str | Path,
    package_name: str | None = None,
    use_ocr: bool = False,
    desktop_target: DesktopTarget | None = None,
    desktop_options: DesktopOptions | None = None,
) -> DesktopCaptureResult:
    resolved_target = desktop_target or resolve_desktop_target()
    resolved_options = desktop_options or resolve_desktop_options()
    capture = capture_bluestacks_window(
        output_path=screenshot_path,
        full_screen_fallback=resolved_options.fullscreen_fallback,
        target=resolved_target,
        options=resolved_options,
    )
    analysis = analyze_screen(
        screenshot_path=capture.output_path,
        package_name=package_name,
        use_ocr=use_ocr,
    )
    visual_state = DesktopVisualState(
        source=f"desktop_{capture.capture_mode}",
        screenshot_path=str(Path(capture.output_path).resolve()),
        capture_mode=capture.capture_mode,
        window=_window_payload(capture.window),
        geometry=get_window_geometry(capture.window) if capture.window else None,
        expected_geometry={
            key: int(value)
            for key, value in {
                "client_width": resolved_options.expected_client_width,
                "client_height": resolved_options.expected_client_height,
            }.items()
            if value is not None
        }
        or None,
        text_signals=list(analysis.ocr_text),
        ocr_status=analysis.ocr_status,
        template_matching_ready=False,
    )
    return DesktopCaptureResult(
        capture=capture,
        analysis=analysis,
        visual_state=visual_state,
    )
