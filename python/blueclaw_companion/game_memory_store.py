from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any


PACKAGE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass
class GameMemory:
    package_name: str
    inferred_genre: str = "unknown"
    genre_confidence: float = 0.0
    observed_states: dict[str, int] = field(default_factory=dict)
    successful_actions: dict[str, dict[str, int]] = field(default_factory=dict)
    failed_actions: dict[str, dict[str, int]] = field(default_factory=dict)
    useful_labels: list[str] = field(default_factory=list)
    state_hints: dict[str, list[str]] = field(default_factory=dict)
    learned_notes: list[str] = field(default_factory=list)
    confidence_trends: list[dict[str, Any]] = field(default_factory=list)
    known_progression_loops: list[str] = field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None
    total_cycles: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sanitize_package_name(package_name: str) -> str:
    cleaned = PACKAGE_FILENAME_RE.sub("_", package_name.strip())
    return cleaned or "unknown-package"


def game_memory_path(game_memory_dir: str | Path, package_name: str) -> Path:
    root = Path(game_memory_dir)
    return root / f"{_sanitize_package_name(package_name)}.json"


def load_game_memory(package_name: str | None, game_memory_dir: str | Path) -> GameMemory | None:
    if not package_name:
        return None
    path = game_memory_path(game_memory_dir, package_name)
    if not path.exists():
        return GameMemory(package_name=package_name)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return GameMemory(
        package_name=payload.get("package_name") or package_name,
        inferred_genre=str(payload.get("inferred_genre", "unknown")),
        genre_confidence=float(payload.get("genre_confidence", 0.0)),
        observed_states={str(key): int(value) for key, value in payload.get("observed_states", {}).items()},
        successful_actions={
            str(state): {str(action): int(count) for action, count in actions.items()}
            for state, actions in payload.get("successful_actions", {}).items()
        },
        failed_actions={
            str(state): {str(action): int(count) for action, count in actions.items()}
            for state, actions in payload.get("failed_actions", {}).items()
        },
        useful_labels=[str(value) for value in payload.get("useful_labels", []) if str(value).strip()],
        state_hints={
            str(state): [str(value) for value in values if str(value).strip()]
            for state, values in payload.get("state_hints", {}).items()
        },
        learned_notes=[str(value) for value in payload.get("learned_notes", []) if str(value).strip()],
        confidence_trends=[
            value for value in payload.get("confidence_trends", []) if isinstance(value, dict)
        ],
        known_progression_loops=[
            str(value) for value in payload.get("known_progression_loops", []) if str(value).strip()
        ],
        first_seen=str(payload["first_seen"]) if payload.get("first_seen") else None,
        last_seen=str(payload["last_seen"]) if payload.get("last_seen") else None,
        total_cycles=int(payload.get("total_cycles", 0)),
    )


def save_game_memory(game_memory_dir: str | Path, memory: GameMemory) -> Path:
    path = game_memory_path(game_memory_dir, memory.package_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def _increment_nested(counter: dict[str, dict[str, int]], state: str, action: str) -> None:
    state_counter = counter.setdefault(state, {})
    state_counter[action] = state_counter.get(action, 0) + 1


def _append_unique(values: list[str], new_values: list[str]) -> list[str]:
    seen = {value.casefold(): value for value in values}
    merged = list(values)
    for value in new_values:
        key = value.strip().casefold()
        if not key or key in seen:
            continue
        seen[key] = value.strip()
        merged.append(value.strip())
    return merged


def preferred_action_for_state(memory: GameMemory | None, state: str) -> str | None:
    if not memory:
        return None
    successes = memory.successful_actions.get(state, {})
    failures = memory.failed_actions.get(state, {})
    ranked: list[tuple[int, str]] = []
    for action, success_count in successes.items():
        score = success_count - failures.get(action, 0)
        if score > 0:
            ranked.append((score, action))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked else None


def update_game_memory(
    memory: GameMemory | None,
    *,
    timestamp: str,
    package_name: str,
    inferred_genre: str,
    genre_confidence: float,
    state: str,
    matched_hints: list[str],
    action: str,
    action_outcome: str,
    state_confidence: float,
    action_confidence: float,
    selected_profile_id: str,
    selected_control_style: str,
    continue_reason: str,
    stop_reason: str | None = None,
    next_state: str | None = None,
) -> GameMemory:
    game_memory = memory or GameMemory(package_name=package_name)
    if not game_memory.first_seen:
        game_memory.first_seen = timestamp
    game_memory.last_seen = timestamp
    game_memory.total_cycles += 1
    game_memory.observed_states[state] = game_memory.observed_states.get(state, 0) + 1
    game_memory.useful_labels = _append_unique(game_memory.useful_labels, matched_hints)

    state_hints = list(game_memory.state_hints.get(state, []))
    game_memory.state_hints[state] = _append_unique(state_hints, matched_hints)

    if inferred_genre != "unknown":
        if game_memory.inferred_genre in {"", "unknown"} or game_memory.inferred_genre == inferred_genre:
            game_memory.inferred_genre = inferred_genre
            game_memory.genre_confidence = max(game_memory.genre_confidence, genre_confidence)
        elif genre_confidence >= game_memory.genre_confidence:
            game_memory.inferred_genre = inferred_genre
            game_memory.genre_confidence = genre_confidence

    trend_entry = {
        "timestamp": timestamp,
        "state": state,
        "state_confidence": round(state_confidence, 4),
        "action": action,
        "action_confidence": round(action_confidence, 4),
        "selected_profile_id": selected_profile_id,
        "selected_control_style": selected_control_style,
        "continue_reason": continue_reason,
        "action_outcome": action_outcome,
    }
    if stop_reason:
        trend_entry["stop_reason"] = stop_reason
    if next_state:
        trend_entry["next_state"] = next_state
        loop_key = f"{state}->{next_state}"
        if loop_key not in game_memory.known_progression_loops:
            game_memory.known_progression_loops.append(loop_key)
    game_memory.confidence_trends.append(trend_entry)
    game_memory.confidence_trends = game_memory.confidence_trends[-50:]

    if action_outcome == "success":
        _increment_nested(game_memory.successful_actions, state, action)
    elif action_outcome == "failed":
        _increment_nested(game_memory.failed_actions, state, action)

    note_parts = [continue_reason]
    if stop_reason:
        note_parts.append(f"stop={stop_reason}")
    note_parts.append(f"profile={selected_profile_id}")
    note_parts.append(f"control={selected_control_style}")
    game_memory.learned_notes = _append_unique(game_memory.learned_notes, ["; ".join(note_parts)])
    game_memory.learned_notes = game_memory.learned_notes[-20:]
    return game_memory
