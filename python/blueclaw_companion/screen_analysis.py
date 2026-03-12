from __future__ import annotations

from dataclasses import asdict, dataclass
import shutil
import subprocess
from pathlib import Path

from .state_classifier import ClassificationResult, classify_state
from .ui_dump_parser import UiDump, load_ui_dump


@dataclass(frozen=True)
class ScreenAnalysis:
    screenshot_path: str | None
    ui_dump_path: str | None
    package_name: str | None
    visible_text: list[str]
    ocr_text: list[str]
    detected_packages: list[str]
    state: str
    confidence: float
    reasons: list[str]
    matched_text: list[str]
    ocr_status: str
    ui_elements: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_ocr_text(screenshot_path: str | None) -> tuple[list[str], str]:
    if not screenshot_path:
        return [], "not_requested"

    screenshot = Path(screenshot_path)
    if not screenshot.exists():
        return [], "missing_screenshot"

    tesseract = shutil.which("tesseract")
    if not tesseract:
        return [], "tesseract_not_installed"

    try:
        result = subprocess.run(
            [tesseract, str(screenshot), "stdout"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return [], "tesseract_failed"

    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return values, "ok"


def analyze_screen(
    screenshot_path: str | None = None,
    ui_dump_path: str | None = None,
    package_name: str | None = None,
    use_ocr: bool = False,
) -> ScreenAnalysis:
    ui_dump: UiDump | None = None
    if ui_dump_path:
        ui_dump = load_ui_dump(ui_dump_path)

    ocr_text, ocr_status = extract_ocr_text(screenshot_path if use_ocr else None)
    classification: ClassificationResult = classify_state(
        ui_dump=ui_dump,
        ocr_texts=ocr_text,
        package_name=package_name,
    )

    visible_text = ui_dump.visible_texts if ui_dump else []
    detected_packages = ui_dump.package_names if ui_dump else []

    return ScreenAnalysis(
        screenshot_path=str(Path(screenshot_path).resolve()) if screenshot_path else None,
        ui_dump_path=str(Path(ui_dump_path).resolve()) if ui_dump_path else None,
        package_name=package_name,
        visible_text=visible_text,
        ocr_text=ocr_text,
        detected_packages=detected_packages,
        state=classification.state,
        confidence=classification.confidence,
        reasons=classification.reasons,
        matched_text=classification.matched_text,
        ocr_status=ocr_status,
        ui_elements=ui_dump.ui_elements if ui_dump else [],
    )
