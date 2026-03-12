from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .action_policy import ActionSuggestion
from .game_profiles import GameProfile
from .game_state import GameStateResult


@dataclass(frozen=True)
class WorkflowMemoryEntry:
    timestamp: str
    profile_id: str
    package_name: str | None
    state: str
    state_confidence: float
    action: str
    action_type: str
    action_confidence: float
    safe_to_apply: bool
    reasons: list[str]
    matched_hints: list[str]
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_memory_entry(path: str | Path, entry: WorkflowMemoryEntry) -> Path:
    memory_path = Path(path)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    with memory_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.to_dict(), ensure_ascii=True) + "\n")
    return memory_path


def build_memory_entry(
    *,
    timestamp: str,
    profile: GameProfile,
    state: GameStateResult,
    action: ActionSuggestion,
    artifact_paths: dict[str, str],
) -> WorkflowMemoryEntry:
    return WorkflowMemoryEntry(
        timestamp=timestamp,
        profile_id=profile.profile_id,
        package_name=state.package_name or profile.package_name,
        state=state.state,
        state_confidence=state.confidence,
        action=action.action,
        action_type=action.action_type,
        action_confidence=action.confidence,
        safe_to_apply=action.safe_to_apply,
        reasons=state.reasons + [action.reason],
        matched_hints=state.matched_hints,
        artifact_paths=artifact_paths,
    )
