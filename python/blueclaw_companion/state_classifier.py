from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ui_dump_parser import UiDump, normalize_text


@dataclass(frozen=True)
class ClassificationResult:
    state: str
    confidence: float
    reasons: list[str]
    matched_text: list[str]


def _contains_any(text: str, values: Iterable[str]) -> bool:
    return any(normalize_text(value) in text for value in values if value)


def _find_matches(source: list[str], expected: Iterable[str]) -> list[str]:
    normalized = {normalize_text(item): item for item in source}
    matches: list[str] = []
    for value in expected:
        key = normalize_text(value)
        if key in normalized and normalized[key] not in matches:
            matches.append(normalized[key])
    return matches


def classify_state(
    ui_dump: UiDump | None,
    ocr_texts: Iterable[str] | None = None,
    package_name: str | None = None,
) -> ClassificationResult:
    xml_texts = ui_dump.visible_texts if ui_dump else []
    ocr_values = [value.strip() for value in (ocr_texts or []) if value and value.strip()]
    combined_texts = xml_texts + [value for value in ocr_values if value not in xml_texts]
    haystack = " ".join(normalize_text(value) for value in combined_texts)

    packages = set(ui_dump.package_names if ui_dump else [])
    if package_name:
        packages.add(package_name.strip())
    package_text = " ".join(sorted(normalize_text(value) for value in packages if value))

    rules: list[tuple[str, float, list[str], list[str], str | None]] = [
        (
            "metamask_sign_screen",
            0.96,
            ["signature request", "sign", "reject", "cancel", "gas fee", "network fee"],
            ["MetaMask sign keywords present"],
            "io.metamask",
        ),
        (
            "metamask_onboarding",
            0.92,
            ["get started", "import an existing wallet", "create a new wallet", "i agree", "no thanks"],
            ["MetaMask onboarding keywords present"],
            "io.metamask",
        ),
        (
            "playstore_app_page",
            0.9,
            ["install", "open", "uninstall", "update", "google play"],
            ["Play Store app page controls present"],
            "com.android.vending",
        ),
        (
            "playstore_search",
            0.86,
            ["search for apps", "search apps", "results for", "apps", "games"],
            ["Play Store search/result labels present"],
            "com.android.vending",
        ),
        (
            "polymarket_market_list",
            0.84,
            ["polymarket", "markets", "volume", "trending", "live"],
            ["Polymarket market list keywords present"],
            "com.polymarket",
        ),
        (
            "game_login",
            0.72,
            ["login", "log in", "sign in", "guest", "server", "start game"],
            ["Game login-like labels present"],
            None,
        ),
        (
            "game_tutorial",
            0.7,
            ["tutorial", "tap to continue", "skip", "next", "battle", "quest"],
            ["Game tutorial-like labels present"],
            None,
        ),
    ]

    for state, confidence, keywords, reasons, package_hint in rules:
        package_ok = True
        if package_hint:
            package_ok = normalize_text(package_hint) in package_text
        keyword_ok = _contains_any(haystack, keywords)
        if package_ok and keyword_ok:
            return ClassificationResult(
                state=state,
                confidence=confidence,
                reasons=reasons,
                matched_text=_find_matches(combined_texts, keywords),
            )

    return ClassificationResult(
        state="unknown",
        confidence=0.2 if combined_texts or packages else 0.0,
        reasons=["No deterministic rule matched the current screen"],
        matched_text=[],
    )
