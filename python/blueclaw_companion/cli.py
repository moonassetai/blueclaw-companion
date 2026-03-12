from __future__ import annotations

import argparse
import json
import sys

from .continuation_rules import RuntimePolicy
from .execution_mode import DesktopOptions, DesktopTarget, resolve_desktop_options, resolve_desktop_target
from .game_profiles import list_game_profiles
from .long_run_policy import run_learning_loop
from .mobile_game_learner import run_learning_cycle
from .runtime_app import (
    capture_runtime,
    click_runtime,
    connect_runtime,
    focus_runtime,
    inspect_runtime,
    learner_runtime,
    render_runtime_result,
    send_key_runtime,
    workflow_runtime,
)
from .screen_analysis import analyze_screen
from .shortcuts import build_shortcut_summary
from .workflow_runner import WorkflowError, run_workflow


def parse_vars(items: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"Expected KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        values[key] = value
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blueclaw-companion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify = subparsers.add_parser("classify", help="Analyze a screenshot and/or UI dump.")
    classify.add_argument("--xml", dest="ui_dump_path")
    classify.add_argument("--screenshot")
    classify.add_argument("--package")
    classify.add_argument("--use-ocr", action="store_true")
    classify.add_argument("--json", action="store_true")

    run = subparsers.add_parser("run", help="Main runtime entrypoint for BlueStacks + desktop control.")
    run_subparsers = run.add_subparsers(dest="run_command", required=True)

    def add_runtime_common(subparser: argparse.ArgumentParser, *, include_profile: bool = False) -> None:
        subparser.add_argument("--mode", choices=["adb", "desktop", "hybrid"], default="hybrid")
        subparser.add_argument("--window-handle", type=int)
        subparser.add_argument("--window-title-contains")
        subparser.add_argument("--expected-client-width", type=int)
        subparser.add_argument("--expected-client-height", type=int)
        subparser.add_argument("--desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_true")
        subparser.add_argument("--no-desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_false")
        subparser.set_defaults(desktop_fullscreen_fallback=None)
        subparser.add_argument("--device")
        subparser.add_argument("--adb-path")
        subparser.add_argument("--json", action="store_true")
        if include_profile:
            subparser.add_argument("--profile", default="generic")

    run_connect = run_subparsers.add_parser("connect", help="Connect to BlueStacks ADB endpoint.")
    run_connect.add_argument("--device")
    run_connect.add_argument("--adb-path")
    run_connect.add_argument("--json", action="store_true")

    run_inspect = run_subparsers.add_parser("inspect", help="Happy-path inspect flow: detect/focus/connect/capture/classify/suggest.")
    add_runtime_common(run_inspect, include_profile=True)
    run_inspect.add_argument("--use-ocr", action="store_true")
    run_inspect.add_argument("--capture-screenshot", action="store_true")
    run_inspect.add_argument("--connect-adb", dest="connect_adb", action="store_true")
    run_inspect.add_argument("--no-connect-adb", dest="connect_adb", action="store_false")
    run_inspect.set_defaults(connect_adb=True)
    run_inspect.add_argument("--focus", dest="focus_window", action="store_true")
    run_inspect.add_argument("--no-focus", dest="focus_window", action="store_false")
    run_inspect.set_defaults(focus_window=True)

    run_capture = run_subparsers.add_parser("capture", help="Capture current state through selected runtime mode.")
    add_runtime_common(run_capture)
    run_capture.add_argument("--output", dest="output_path")
    run_capture.add_argument("--use-ocr", action="store_true")
    run_capture.add_argument("--connect-adb", action="store_true")

    run_learner = run_subparsers.add_parser("learner", help="Run learner through runtime command flow.")
    add_runtime_common(run_learner, include_profile=True)
    run_learner.add_argument("--use-ocr", action="store_true")
    run_learner.add_argument("--capture-screenshot", action="store_true")
    run_learner.add_argument("--connect-adb", dest="connect_adb", action="store_true")
    run_learner.add_argument("--no-connect-adb", dest="connect_adb", action="store_false")
    run_learner.set_defaults(connect_adb=True)
    run_learner.add_argument("--execute-safe-actions", action="store_true")

    run_workflow = run_subparsers.add_parser("workflow", help="Run workflow through runtime command flow.")
    add_runtime_common(run_workflow)
    run_workflow.add_argument("workflow_name")
    run_workflow.add_argument("--var", action="append", default=[], help="Workflow variable override in KEY=VALUE form.")
    run_workflow.add_argument("--connect-adb", dest="connect_adb", action="store_true")
    run_workflow.add_argument("--no-connect-adb", dest="connect_adb", action="store_false")
    run_workflow.set_defaults(connect_adb=True)
    run_workflow.add_argument("--dry-run", action="store_true")
    run_workflow.add_argument("--approve-sensitive", action="store_true")
    run_workflow.add_argument("--approve-all-boundaries", action="store_true")

    run_focus = run_subparsers.add_parser("focus", help="Focus BlueStacks window.")
    add_runtime_common(run_focus)

    run_send_key = run_subparsers.add_parser("send-key", help="Send key input to BlueStacks window.")
    add_runtime_common(run_send_key)
    run_send_key.add_argument("--key", required=True)
    run_send_key.add_argument("--repeat-count", type=int, default=1)
    run_send_key.add_argument("--delay-ms", type=int, default=120)

    run_click = run_subparsers.add_parser("click", help="Click BlueStacks client-relative coordinates.")
    add_runtime_common(run_click)
    run_click.add_argument("--x", type=int, required=True)
    run_click.add_argument("--y", type=int, required=True)
    run_click.add_argument("--repeat-count", type=int, default=1)
    run_click.add_argument("--delay-ms", type=int, default=120)

    workflow = subparsers.add_parser("workflow", help="Run an explicit Phase 2 workflow.")
    workflow_subparsers = workflow.add_subparsers(dest="workflow_command", required=True)

    run_cmd = workflow_subparsers.add_parser("run", help="Run a workflow definition.")
    run_cmd.add_argument("--workflow", required=True)
    run_cmd.add_argument("--var", action="append", default=[], help="Workflow variable override in KEY=VALUE form.")
    run_cmd.add_argument("--dry-run", action="store_true")
    run_cmd.add_argument("--approve-sensitive", action="store_true")
    run_cmd.add_argument("--approve-all-boundaries", action="store_true")
    run_cmd.add_argument("--execution-mode", choices=["adb", "desktop"], default="adb")
    run_cmd.add_argument("--window-handle", type=int)
    run_cmd.add_argument("--window-title-contains")
    run_cmd.add_argument("--expected-client-width", type=int)
    run_cmd.add_argument("--expected-client-height", type=int)
    run_cmd.add_argument("--desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_true")
    run_cmd.add_argument("--no-desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_false")
    run_cmd.set_defaults(desktop_fullscreen_fallback=None)
    run_cmd.add_argument("--json", action="store_true")

    learner = subparsers.add_parser("learner", help="Run the mobile game learner layer.")
    learner_subparsers = learner.add_subparsers(dest="learner_command", required=True)

    learner_run = learner_subparsers.add_parser("run", help="Classify a mobile game screen and suggest the next action.")
    learner_run.add_argument("--profile", default="generic")
    learner_run.add_argument("--profile-path")
    learner_run.add_argument("--memory-path")
    learner_run.add_argument("--xml", dest="ui_dump_path")
    learner_run.add_argument("--screenshot")
    learner_run.add_argument("--package")
    learner_run.add_argument("--ui-text")
    learner_run.add_argument("--use-ocr", action="store_true")
    learner_run.add_argument("--capture", action="store_true")
    learner_run.add_argument("--connect", action="store_true")
    learner_run.add_argument("--capture-screenshot", action="store_true")
    learner_run.add_argument("--control-mode", choices=["adb", "desktop"], default="adb")
    learner_run.add_argument("--window-handle", type=int)
    learner_run.add_argument("--window-title-contains")
    learner_run.add_argument("--expected-client-width", type=int)
    learner_run.add_argument("--expected-client-height", type=int)
    learner_run.add_argument("--desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_true")
    learner_run.add_argument("--no-desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_false")
    learner_run.set_defaults(desktop_fullscreen_fallback=None)
    learner_run.add_argument("--game-memory-dir")
    learner_run.add_argument("--execute-safe-actions", action="store_true")
    learner_run.add_argument("--json", action="store_true")

    learner_loop = learner_subparsers.add_parser("loop", help="Run conservative long-running learner cycles.")
    learner_loop.add_argument("--profile", default="generic")
    learner_loop.add_argument("--profile-path")
    learner_loop.add_argument("--memory-path")
    learner_loop.add_argument("--game-memory-dir")
    learner_loop.add_argument("--xml", dest="ui_dump_path")
    learner_loop.add_argument("--screenshot")
    learner_loop.add_argument("--package")
    learner_loop.add_argument("--ui-text")
    learner_loop.add_argument("--use-ocr", action="store_true")
    learner_loop.add_argument("--capture", action="store_true")
    learner_loop.add_argument("--connect", action="store_true")
    learner_loop.add_argument("--capture-screenshot", action="store_true")
    learner_loop.add_argument("--control-mode", choices=["adb", "desktop"], default="adb")
    learner_loop.add_argument("--window-handle", type=int)
    learner_loop.add_argument("--window-title-contains")
    learner_loop.add_argument("--expected-client-width", type=int)
    learner_loop.add_argument("--expected-client-height", type=int)
    learner_loop.add_argument("--desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_true")
    learner_loop.add_argument("--no-desktop-fullscreen-fallback", dest="desktop_fullscreen_fallback", action="store_false")
    learner_loop.set_defaults(desktop_fullscreen_fallback=None)
    learner_loop.add_argument("--max-auto-cycles", type=int)
    learner_loop.add_argument("--max-repeated-state-count", type=int)
    learner_loop.add_argument("--max-repeated-action-count", type=int)
    learner_loop.add_argument("--max-no-progress-cycles", type=int)
    learner_loop.add_argument("--min-state-confidence", type=float)
    learner_loop.add_argument("--min-action-confidence", type=float)
    learner_loop.add_argument("--stop-on-risky-action", action="store_true")
    learner_loop.add_argument("--unknown-streak-limit", type=int)
    learner_loop.add_argument("--low-confidence-streak-limit", type=int)
    learner_loop.add_argument("--json", action="store_true")

    learner_profiles = learner_subparsers.add_parser("profiles", help="List available learner profiles.")
    learner_profiles.add_argument("--profile-path")

    shortcuts = subparsers.add_parser("shortcuts", help="Inspect shortcut acceleration backend plans.")
    shortcuts_subparsers = shortcuts.add_subparsers(dest="shortcuts_command", required=True)
    shortcuts_status = shortcuts_subparsers.add_parser("status", help="Show current shortcut backend resolution.")
    shortcuts_status.add_argument("--mode", choices=["adb", "desktop"], default="adb")
    shortcuts_status.add_argument("--use-ocr", action="store_true")
    shortcuts_status.add_argument("--prefer-scrcpy", action="store_true")
    shortcuts_status.add_argument("--prefer-vision-model", action="store_true")
    shortcuts_status.add_argument("--json", action="store_true")

    return parser


def build_runtime_policy(args: argparse.Namespace) -> RuntimePolicy:
    policy = RuntimePolicy()
    values = policy.to_dict()
    overrides = {
        "max_auto_cycles": getattr(args, "max_auto_cycles", None),
        "max_repeated_state_count": getattr(args, "max_repeated_state_count", None),
        "max_repeated_action_count": getattr(args, "max_repeated_action_count", None),
        "max_no_progress_cycles": getattr(args, "max_no_progress_cycles", None),
        "min_state_confidence": getattr(args, "min_state_confidence", None),
        "min_action_confidence": getattr(args, "min_action_confidence", None),
        "unknown_streak_limit": getattr(args, "unknown_streak_limit", None),
        "low_confidence_streak_limit": getattr(args, "low_confidence_streak_limit", None),
    }
    for key, value in overrides.items():
        if value is not None:
            values[key] = value
    if getattr(args, "stop_on_risky_action", False):
        values["stop_on_risky_action"] = True
    return RuntimePolicy(**values)


def resolve_desktop_configuration(args: argparse.Namespace) -> tuple[DesktopTarget, DesktopOptions]:
    target = resolve_desktop_target(
        window_handle=getattr(args, "window_handle", None),
        window_title_contains=getattr(args, "window_title_contains", None),
    )
    options = resolve_desktop_options(
        fullscreen_fallback=getattr(args, "desktop_fullscreen_fallback", None),
        expected_client_width=getattr(args, "expected_client_width", None),
        expected_client_height=getattr(args, "expected_client_height", None),
    )
    return target, options


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "classify":
        result = analyze_screen(
            screenshot_path=args.screenshot,
            ui_dump_path=args.ui_dump_path,
            package_name=args.package,
            use_ocr=args.use_ocr,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"State: {result.state}")
            print(f"Confidence: {result.confidence:.2f}")
            print(f"Package hint: {result.package_name or 'n/a'}")
            print(f"OCR status: {result.ocr_status}")
            if result.matched_text:
                print("Matched text: " + ", ".join(result.matched_text))
            if result.reasons:
                print("Reasons: " + "; ".join(result.reasons))
            if result.visible_text:
                preview = ", ".join(result.visible_text[:10])
                print(f"Visible text: {preview}")
        return 0

    if args.command == "run":
        try:
            if args.run_command == "connect":
                payload = connect_runtime(device=args.device, adb_path=args.adb_path)
            else:
                desktop_target, desktop_options = resolve_desktop_configuration(args)
                if args.run_command == "inspect":
                    payload = inspect_runtime(
                        mode=args.mode,
                        profile=args.profile,
                        use_ocr=args.use_ocr,
                        capture_screenshot=args.capture_screenshot,
                        connect_adb=args.connect_adb,
                        focus_window=args.focus_window,
                        device=args.device,
                        adb_path=args.adb_path,
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                elif args.run_command == "capture":
                    payload = capture_runtime(
                        mode=args.mode,
                        output_path=args.output_path,
                        use_ocr=args.use_ocr,
                        connect_adb=args.connect_adb,
                        device=args.device,
                        adb_path=args.adb_path,
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                elif args.run_command == "learner":
                    payload = learner_runtime(
                        mode=args.mode,
                        profile=args.profile,
                        use_ocr=args.use_ocr,
                        capture_screenshot=args.capture_screenshot,
                        connect_adb=args.connect_adb,
                        device=args.device,
                        adb_path=args.adb_path,
                        execute_safe_actions=args.execute_safe_actions,
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                elif args.run_command == "workflow":
                    payload = workflow_runtime(
                        mode=args.mode,
                        workflow_name=args.workflow_name,
                        vars_items=args.var,
                        connect_adb=args.connect_adb,
                        device=args.device,
                        adb_path=args.adb_path,
                        dry_run=args.dry_run,
                        approve_sensitive=args.approve_sensitive,
                        approve_all_boundaries=args.approve_all_boundaries,
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                elif args.run_command == "focus":
                    payload = focus_runtime(
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                elif args.run_command == "send-key":
                    payload = send_key_runtime(
                        key=args.key,
                        repeat_count=args.repeat_count,
                        delay_ms=args.delay_ms,
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                elif args.run_command == "click":
                    payload = click_runtime(
                        x=args.x,
                        y=args.y,
                        repeat_count=args.repeat_count,
                        delay_ms=args.delay_ms,
                        desktop_target=desktop_target,
                        desktop_options=desktop_options,
                    )
                else:
                    parser.error(f"Unsupported run command: {args.run_command}")
                    return 1
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(render_runtime_result(payload))
        return 0

    if args.command == "workflow" and args.workflow_command == "run":
        variables = parse_vars(args.var)
        desktop_target, desktop_options = resolve_desktop_configuration(args)
        try:
            result = run_workflow(
                workflow_name=args.workflow,
                variable_overrides=variables,
                dry_run=args.dry_run,
                approve_sensitive=args.approve_sensitive,
                approve_all_boundaries=args.approve_all_boundaries,
                execution_mode=args.execution_mode,
                desktop_target=desktop_target,
                desktop_options=desktop_options,
            )
        except WorkflowError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Workflow: {result.workflow}")
            print(f"Status: {result.status}")
            print(f"Message: {result.message}")
            if result.next_step:
                print(f"Next step: {result.next_step}")
            if result.analysis:
                print(f"Detected state: {result.analysis['state']}")
        return 0

    if args.command == "learner" and args.learner_command == "run":
        desktop_target, desktop_options = resolve_desktop_configuration(args)
        result = run_learning_cycle(
            profile_id=args.profile,
            ui_dump_path=args.ui_dump_path,
            screenshot_path=args.screenshot,
            package_name=args.package,
            ui_text=args.ui_text,
            profile_path=args.profile_path,
            memory_path=args.memory_path,
            game_memory_dir=args.game_memory_dir,
            use_ocr=args.use_ocr,
            connect=args.connect,
            capture=args.capture,
            capture_screenshot=args.capture_screenshot,
            control_mode=args.control_mode,
            desktop_target=desktop_target,
            desktop_options=desktop_options,
            execute_safe_actions=args.execute_safe_actions,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Profile: {result.profile['profile_id']}")
            print(f"Inferred genre: {result.genre['genre_id'] if result.genre else 'unknown'}")
            print(f"Detected state: {result.state['state']}")
            print(f"State confidence: {result.state['confidence']:.2f}")
            print(f"Selected profile: {result.selected_profile_id}")
            print(f"Suggested action: {result.action['action']}")
            print(f"Action type: {result.action['action_type']}")
            print(f"Safe to apply: {result.action['safe_to_apply']}")
            print(f"Decision: {result.decision['decision']}")
            print(f"Reason: {result.decision['reason']}")
            print(f"Executed: {result.execution['executed']}")
            print(f"Memory: {result.memory_path}")
            if result.game_memory_path:
                print(f"Game memory: {result.game_memory_path}")
        return 0

    if args.command == "learner" and args.learner_command == "loop":
        desktop_target, desktop_options = resolve_desktop_configuration(args)
        result = run_learning_loop(
            profile_id=args.profile,
            profile_path=args.profile_path,
            memory_path=args.memory_path,
            game_memory_dir=args.game_memory_dir,
            ui_dump_path=args.ui_dump_path,
            screenshot_path=args.screenshot,
            package_name=args.package,
            ui_text=args.ui_text,
            use_ocr=args.use_ocr,
            connect=args.connect,
            capture=args.capture,
            capture_screenshot=args.capture_screenshot,
            control_mode=args.control_mode,
            desktop_target=desktop_target,
            desktop_options=desktop_options,
            execute_safe_actions=True,
            policy=build_runtime_policy(args),
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Cycles: {result.cycle_count}")
            print(f"Last stop reason: {result.last_stop_reason}")
            print(f"Cycle log: {result.memory_path}")
            print(f"Game memory dir: {result.game_memory_dir}")
        return 0

    if args.command == "learner" and args.learner_command == "profiles":
        profiles = list_game_profiles(path=args.profile_path)
        for profile in profiles:
            print(profile)
        return 0

    if args.command == "shortcuts" and args.shortcuts_command == "status":
        summary = build_shortcut_summary(
            execution_mode=args.mode,
            use_ocr=args.use_ocr,
            prefer_scrcpy=args.prefer_scrcpy,
            prefer_vision_model=args.prefer_vision_model,
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            perception = summary["perception"]
            control = summary["control"]
            print(f"Perception capture backend: {perception['capture_backend']}")
            print(f"Perception OCR backend: {perception['ocr_backend']}")
            print(f"Perception vision backend: {perception['vision_backend']}")
            print(f"Control backend: {control['control_backend']}")
            print(f"scrcpy available: {control['scrcpy_available']}")
        return 0

    parser.print_help()
    return 1
