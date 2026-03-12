from __future__ import annotations

from typing import Iterable

from .genre_profiles import GENRE_PROFILES
from .ui_dump_parser import normalize_text


PACKAGE_HINTS = {
    "idle": "idle_rpg",
    "afk": "idle_rpg",
    "rpg": "action_rpg",
    "city": "city_builder",
    "clash": "strategy_rts",
    "puzzle": "match3_puzzle",
    "match": "match3_puzzle",
    "casino": "social_casino",
    "slots": "social_casino",
    "shooter": "fps_shooter",
    "survival": "survival_crafting",
    "craft": "survival_crafting",
    "tycoon": "tycoon_management",
    "racing": "racing",
    "sports": "sports_manager",
    "td": "tower_defense",
    "defense": "tower_defense",
    "moba": "moba",
}


def classify_genre(
    package_name: str | None,
    visible_texts: Iterable[str],
    current_state: str | None = None,
) -> str:
    """Infer the game genre based on package name heuristics and visible UI text."""
    # 1. Check package name
    if package_name:
        normalized_pkg = package_name.lower()
        for hint, genre_id in PACKAGE_HINTS.items():
            if hint in normalized_pkg:
                return genre_id
                
    # 2. Check UI text via scoring
    combined_text = " ".join(normalize_text(t) for t in visible_texts if normalize_text(t))
    if not combined_text:
        return "unknown"
        
    scores: dict[str, int] = {}
    for profile in GENRE_PROFILES:
        score = 0
        for label in profile.common_labels:
            if normalize_text(label) in combined_text:
                score += 1
        if score > 0:
            scores[profile.genre_id] = score
            
    if scores:
        # Get highest score; fallback to unknown if tied lightly
        top_genre = max(scores.items(), key=lambda x: x[1])[0]
        return top_genre
        
    return "unknown"
