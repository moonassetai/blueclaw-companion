from __future__ import annotations

import argparse
import json
import sys

from .game_profiles import list_game_profiles
from .mobile_game_learner import run_learning_cycle
from .screen_analysis import analyze_screen
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

    workflow = subparsers.add_parser("workflow", help="Run an explicit Phase 2 workflow.")
    workflow_subparsers = workflow.add_subparsers(dest="workflow_command", required=True)

    run_cmd = workflow_subparsers.add_parser("run", help="Run a workflow definition.")
    run_cmd.add_argument("--workflow", required=True)
    run_cmd.add_argument("--var", action="append", default=[], help="Workflow variable override in KEY=VALUE form.")
    run_cmd.add_argument("--dry-run", action="store_true")
    run_cmd.add_argument("--approve-sensitive", action="store_true")
    run_cmd.add_argument("--approve-all-boundaries", action="store_true")
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
    learner_run.add_argument("--json", action="store_true")

    learner_profiles = learner_subparsers.add_parser("profiles", help="List available learner profiles.")
    learner_profiles.add_argument("--profile-path")

    return parser


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

    if args.command == "workflow" and args.workflow_command == "run":
        variables = parse_vars(args.var)
        try:
            result = run_workflow(
                workflow_name=args.workflow,
                variable_overrides=variables,
                dry_run=args.dry_run,
                approve_sensitive=args.approve_sensitive,
                approve_all_boundaries=args.approve_all_boundaries,
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
        result = run_learning_cycle(
            profile_id=args.profile,
            ui_dump_path=args.ui_dump_path,
            screenshot_path=args.screenshot,
            package_name=args.package,
            ui_text=args.ui_text,
            profile_path=args.profile_path,
            memory_path=args.memory_path,
            use_ocr=args.use_ocr,
            connect=args.connect,
            capture=args.capture,
            capture_screenshot=args.capture_screenshot,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Profile: {result.profile['profile_id']}")
            print(f"Detected state: {result.state['state']}")
            print(f"State confidence: {result.state['confidence']:.2f}")
            print(f"Suggested action: {result.action['action']}")
            print(f"Action type: {result.action['action_type']}")
            print(f"Safe to apply: {result.action['safe_to_apply']}")
            print(f"Memory: {result.memory_path}")
        return 0

    if args.command == "learner" and args.learner_command == "profiles":
        profiles = list_game_profiles(path=args.profile_path)
        for profile in profiles:
            print(profile)
        return 0

    parser.print_help()
    return 1
