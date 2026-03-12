from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .screen_analysis import ScreenAnalysis
from .ui_dump_parser import normalize_text


KNOWN_GAME_STATES = (
    "loading",
    "login",
    "tutorial",
    "battle",
    "reward",
    "menu",
    "upgrade",
    "unknown",
)


DEFAULT_STATE_HINTS: dict[str, list[str]] = {
    "loading": ["loading", "connecting", "downloading", "checking resources", "tap to start"],
    "login": ["login", "log in", "sign in", "guest", "server", "account", "start game"],
    "tutorial": ["tutorial", "tap to continue", "skip", "next", "guide", "quest", "mission"],
    "battle": ["battle", "fight", "combat", "auto", "stage", "victory", "defeat"],
    "reward": ["reward", "claim", "collect", "bonus", "receive", "chest"],
    "menu": ["menu", "shop", "inventory", "mission", "summon", "campaign", "home"],
    "upgrade": ["upgrade", "enhance", "level up", "power up", "equipment", "confirm"],
}


@dataclass(frozen=True)
class GameStateResult:
    state: str
    confidence: float
    reasons: list[str]
    matched_hints: list[str]
    package_name: str | None
    visible_text: list[str]
    classifier_state: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _find_matches(texts: Iterable[str], hints: Iterable[str]) -> list[str]:
    normalized_texts = {normalize_text(text): text for text in texts if normalize_text(text)}
    matches: list[str] = []
    for hint in hints:
        normalized_hint = normalize_text(hint)
        for key, original in normalized_texts.items():
            if normalized_hint and normalized_hint in key and original not in matches:
                matches.append(original)
    return matches


def classify_game_state(
    analysis: ScreenAnalysis,
    state_hints: dict[str, list[str]] | None = None,
    ui_text: str | None = None,
) -> GameStateResult:
    hints = {key: list(value) for key, value in DEFAULT_STATE_HINTS.items()}
    for state, values in (state_hints or {}).items():
        if state not in KNOWN_GAME_STATES:
            continue
        hints.setdefault(state, [])
        for value in values:
            if value not in hints[state]:
                hints[state].append(value)

    combined_text = list(analysis.visible_text)
    if ui_text:
        combined_text.extend(line.strip() for line in ui_text.splitlines() if line.strip())
    if analysis.ocr_text:
        combined_text.extend(value for value in analysis.ocr_text if value not in combined_text)

    normalized_haystack = " ".join(normalize_text(value) for value in combined_text)

    classifier_mapping = {
        "game_login": "login",
        "game_tutorial": "tutorial",
    }
    mapped_state = classifier_mapping.get(analysis.state)
    if mapped_state:
        return GameStateResult(
            state=mapped_state,
            confidence=max(analysis.confidence, 0.72),
            reasons=[f"Phase 2 classifier mapped `{analysis.state}` to `{mapped_state}`."],
            matched_hints=analysis.matched_text,
            package_name=analysis.package_name,
            visible_text=combined_text,
            classifier_state=analysis.state,
        )

    scored_states: list[tuple[str, float, list[str]]] = []
    for state in KNOWN_GAME_STATES:
        if state == "unknown":
            continue
        matches = _find_matches(combined_text, hints.get(state, []))
        if not matches:
            continue
        score = min(0.55 + (0.12 * len(matches)), 0.95)
        scored_states.append((state, score, matches))

    if scored_states:
        scored_states.sort(key=lambda item: item[1], reverse=True)
        state, confidence, matches = scored_states[0]
        return GameStateResult(
            state=state,
            confidence=confidence,
            reasons=[f"Matched {len(matches)} hint(s) for `{state}` in the current UI text."],
            matched_hints=matches,
            package_name=analysis.package_name,
            visible_text=combined_text,
            classifier_state=analysis.state,
        )

    if analysis.state == "unknown" and not normalized_haystack:
        return GameStateResult(
            state="loading",
            confidence=0.35,
            reasons=["No visible text was extracted; treating the screen as loading-like until more evidence exists."],
            matched_hints=[],
            package_name=analysis.package_name,
            visible_text=combined_text,
            classifier_state=analysis.state,
        )

    return GameStateResult(
        state="unknown",
        confidence=min(analysis.confidence, 0.4),
        reasons=["No game-state rule matched. Conservative fallback is `unknown`."],
        matched_hints=[],
        package_name=analysis.package_name,
        visible_text=combined_text,
        classifier_state=analysis.state,
    )
