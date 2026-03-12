"""Blueclaw Companion Phase 2."""

from .execution_mode import DesktopOptions, DesktopTarget, ExecutionMode
from .shortcuts import build_shortcut_summary, list_shortcut_capabilities
from .screen_analysis import analyze_screen
from .state_classifier import classify_state
from .long_run_policy import run_learning_loop
from .mobile_game_learner import run_learning_cycle

__all__ = [
    "analyze_screen",
    "classify_state",
    "run_learning_cycle",
    "run_learning_loop",
    "ExecutionMode",
    "DesktopTarget",
    "DesktopOptions",
    "list_shortcut_capabilities",
    "build_shortcut_summary",
]
