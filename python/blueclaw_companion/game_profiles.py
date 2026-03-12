from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from .game_state import KNOWN_GAME_STATES


ROOT_DIR = Path(__file__).resolve().parents[2]
PROFILE_REGISTRY_PATH = ROOT_DIR / "workflows" / "mobile-game-learner.json"


@dataclass(frozen=True)
class ActionTarget:
    action: str
    type: str = "tap"
    x: int | None = None
    y: int | None = None
    labels: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GameProfile:
    profile_id: str
    package_name: str | None
    known_state_hints: dict[str, list[str]]
    action_targets: dict[str, ActionTarget]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action_targets"] = {
            key: target.to_dict() for key, target in self.action_targets.items()
        }
        return data


def _validate_states(hints: dict[str, list[str]]) -> dict[str, list[str]]:
    validated: dict[str, list[str]] = {}
    for state, values in hints.items():
        if state not in KNOWN_GAME_STATES:
            continue
        validated[state] = [str(value) for value in values if str(value).strip()]
    return validated


def load_profile_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else PROFILE_REGISTRY_PATH
    return json.loads(registry_path.read_text(encoding="utf-8"))


def load_game_profile(profile_id: str = "generic", path: str | Path | None = None) -> GameProfile:
    registry = load_profile_registry(path)
    profiles = registry.get("profiles", {})
    if profile_id not in profiles:
        available = ", ".join(sorted(profiles)) or "none"
        raise ValueError(f"Unknown game profile `{profile_id}`. Available profiles: {available}")

    raw = profiles[profile_id]
    targets = {
        action: ActionTarget(action=action, **config)
        for action, config in raw.get("action_targets", {}).items()
    }
    return GameProfile(
        profile_id=profile_id,
        package_name=raw.get("package_name"),
        known_state_hints=_validate_states(raw.get("known_state_hints", {})),
        action_targets=targets,
        notes=str(raw.get("notes", "")),
    )


def list_game_profiles(path: str | Path | None = None) -> list[str]:
    registry = load_profile_registry(path)
    return sorted(registry.get("profiles", {}).keys())
