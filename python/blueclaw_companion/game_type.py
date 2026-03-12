from __future__ import annotations

from dataclasses import asdict, dataclass, field

@dataclass(frozen=True)
class GenreProfile:
    genre_id: str
    description: str
    common_ui_states: list[str]
    common_labels: list[str]
    control_style: str
    safe_default_actions: list[str]
    risky_actions: list[str]
    progression_loop: str
    reward_patterns: str
    upgrade_patterns: str
    progression_path: list[str] = field(default_factory=list)
    reward_loop: list[str] = field(default_factory=list)
    upgrade_loop: list[str] = field(default_factory=list)
    safe_repeat_actions: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
