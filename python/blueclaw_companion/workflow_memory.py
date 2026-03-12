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
    inferred_genre_id: str
    profile_id: str
    selected_profile_id: str
    selected_control_style: str
    package_name: str | None
    state: str
    state_confidence: float
    action: str
    action_type: str
    action_confidence: float
    safe_to_apply: bool
    decision: str
    decision_reason: str
    continue_reason: str
    stop_reason: str | None
    executed: bool
    execution_outcome: str
    cycle_index: int | None
    next_state: str | None
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
    decision: str,
    decision_reason: str,
    continue_reason: str,
    stop_reason: str | None,
    executed: bool,
    execution_outcome: str,
    cycle_index: int | None,
    next_state: str | None,
    artifact_paths: dict[str, str],
) -> WorkflowMemoryEntry:
    return WorkflowMemoryEntry(
        timestamp=timestamp,
        inferred_genre_id=action.inferred_genre_id or "unknown",
        profile_id=profile.profile_id,
        selected_profile_id=action.selected_profile_id,
        selected_control_style=action.selected_control_style,
        package_name=state.package_name or profile.package_name,
        state=state.state,
        state_confidence=state.confidence,
        action=action.action,
        action_type=action.action_type,
        action_confidence=action.confidence,
        safe_to_apply=action.safe_to_apply,
        decision=decision,
        decision_reason=decision_reason,
        continue_reason=continue_reason,
        stop_reason=stop_reason,
        executed=executed,
        execution_outcome=execution_outcome,
        cycle_index=cycle_index,
        next_state=next_state,
        reasons=state.reasons + [action.reason, decision_reason],
        matched_hints=state.matched_hints,
        artifact_paths=artifact_paths,
    )
