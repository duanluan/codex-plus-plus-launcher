from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from codex_plus_plus_launcher import __version__
from codex_plus_plus_launcher.doctor import doctor_report
from codex_plus_plus_launcher.runtime import (
    cleanup_legacy_windows_auto_inject,
    command_cwd,
    detect_codex_installation,
    ensure_home,
    install_app,
    remove_broken_windows_npm_shims,
    restart_codex_app,
    start_codex_app,
    runtime_paths,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex++ launcher wrapper")
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser("install-app", help="Install Codex++ into the local Codex App when possible")
    install_parser.add_argument("--from-postinstall", action="store_true", help=argparse.SUPPRESS)

    repair_parser = subparsers.add_parser("repair-app", help="Repair the local Codex++ app integration")
    repair_parser.add_argument("--from-postinstall", action="store_true", help=argparse.SUPPRESS)

    setup_parser = subparsers.add_parser("setup", help="Deprecated alias of install-app")
    setup_parser.add_argument("--from-postinstall", action="store_true", help=argparse.SUPPRESS)

    legacy_repair_parser = subparsers.add_parser("repair", help="Deprecated alias of repair-app")
    legacy_repair_parser.add_argument("--from-postinstall", action="store_true", help=argparse.SUPPRESS)

    doctor_parser = subparsers.add_parser("doctor", help="Inspect local runtime state")
    doctor_parser.add_argument("--json", action="store_true")

    launch_parser = subparsers.add_parser("launch", help="Launch upstream Codex++")
    launch_parser.add_argument("args", nargs=argparse.REMAINDER)

    run_parser = subparsers.add_parser("run", help="Alias of launch")
    run_parser.add_argument("args", nargs=argparse.REMAINDER)

    help_parser = subparsers.add_parser("help", help="Show top-level or subcommand help")
    help_parser.add_argument("topic", nargs="?")

    subparsers.add_parser("version", help="Print version")
    return parser


def print_version() -> int:
    print(__version__)
    return 0


def cleanup_windows_npm_conflicts() -> None:
    removed = remove_broken_windows_npm_shims()
    if removed:
        print("removed broken npm launcher shims:")
        for path in removed:
            print(path)


def running_as_frozen_binary() -> bool:
    return bool(getattr(sys, "frozen", False))


def run_bundled_upstream(args: list[str]) -> int:
    from codex_session_delete import cli as upstream_cli

    upstream_cli.maybe_print_update_notice = lambda: None
    return int(upstream_cli.main(normalize_passthrough_args(args)))


def print_deprecated_alias(alias: str, target: str) -> None:
    print(f"`cxpp {alias}` is deprecated; using `cxpp {target}`.")


def normalize_passthrough_args(values: list[str]) -> list[str]:
    if values and values[0] == "--":
        return values[1:]
    return values


def _is_interactive_terminal() -> bool:
    return sys.stdin is not None and sys.stdin.isatty() and sys.stdout is not None and sys.stdout.isatty()


def _prompt_restart() -> bool:
    if not _is_interactive_terminal():
        return False
    try:
        answer = input("Codex App is running. Restart it now to load Codex++? [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _prompt_launch() -> bool:
    if not _is_interactive_terminal():
        return False
    try:
        answer = input("Codex++ is ready. Launch it now? [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _print_install_result(result, from_postinstall: bool = False) -> int:
    print(f"install_mode={result.mode}")
    print(f"app_integration_state={result.app_integration_state}")
    print(f"restart_required={'yes' if result.restart_required else 'no'}")
    print(f"state_dir={result.state_dir}")
    if result.app_dir is not None:
        print(f"app_dir={result.app_dir}")
    if result.codex_binary is not None:
        print(f"app_binary={result.codex_binary}")
    print(f"shortcut_state={result.shortcut_state}")
    print(f"start_menu_state={result.start_menu_state}")
    print(f"shortcut_icon_state={result.shortcut_icon_state}")
    print(f"legacy_auto_inject={result.legacy_auto_inject_state}")
    if result.expected_launcher_version is not None:
        print(f"expected_launcher_version={result.expected_launcher_version}")
    if result.global_command_version is not None:
        print(f"global_command_version={result.global_command_version}")
    if result.shortcut_binary_version is not None:
        print(f"shortcut_binary_version={result.shortcut_binary_version}")
    print(f"stale_global_binaries={result.stale_global_binaries}")
    if result.shortcut_target is not None:
        print(f"shortcut_target={result.shortcut_target}")
    if result.shortcut_launcher is not None:
        print(f"shortcut_launcher={result.shortcut_launcher}")
    if result.shortcut_icon is not None:
        print(f"shortcut_icon={result.shortcut_icon}")
    if result.fallback_reason:
        print(f"fallback_reason={result.fallback_reason}")
    if result.message:
        print(result.message)

    if result.mode == "external_launch" and result.app_integration_state in {"fallback", "missing"}:
        print("Use `cxpp launch` to run Codex++ explicitly.")

    if result.global_command_version and result.expected_launcher_version and result.global_command_version != result.expected_launcher_version:
        print(
            "Detected a mismatched global cxpp command version. Reinstall the npm package globally and verify with `npm list -g @duanluan/codex-plus-plus-launcher`."
        )

    if result.restart_required:
        installation = detect_codex_installation()
        if _prompt_restart():
            if restart_codex_app(installation):
                print("Codex App was restarted.")
            else:
                print("Failed to restart Codex App automatically. Please restart it manually.")
        else:
            print("Please restart Codex App manually to load the latest Codex++ integration.")
    else:
        if from_postinstall:
            if _prompt_launch():
                installation = detect_codex_installation()
                if start_codex_app(installation):
                    print("Codex++ was launched.")
                else:
                    print("Failed to launch Codex++ automatically. Run `cxpp launch` or open the Codex++ shortcut.")
            else:
                print("Run `cxpp launch` or open the Codex++ shortcut when you are ready.")

    return 0


def run_install_app(repair: bool = False, from_postinstall: bool = False, shortcut_mode: str = "real") -> int:
    cleanup_windows_npm_conflicts()
    paths = runtime_paths()
    ensure_home(paths)
    cleanup_legacy_windows_auto_inject()
    result = install_app(paths, repair=repair, from_postinstall=from_postinstall, shortcut_mode=shortcut_mode)
    return _print_install_result(result, from_postinstall=from_postinstall)


def run_npm_postinstall() -> int:
    cleanup_windows_npm_conflicts()
    paths = runtime_paths()
    ensure_home(paths)
    cleanup_legacy_windows_auto_inject()
    shortcut_mode = "skip" if os.environ.get("CODEXPP_SHORTCUT_MODE") == "skip" else "real"
    result = install_app(paths, repair=False, from_postinstall=True, shortcut_mode=shortcut_mode)
    return _print_install_result(result, from_postinstall=True)


def run_doctor(json_mode: bool = False) -> int:
    cleanup_windows_npm_conflicts()
    report = doctor_report()
    if json_mode:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    for key, value in report.items():
        print(f"{key}={value}")
    return 0


def run_fast_launch(args: list[str]) -> int:
    if running_as_frozen_binary():
        return run_bundled_upstream(["launch", *normalize_passthrough_args(args)])
    cleanup_windows_npm_conflicts()
    paths = runtime_paths()
    ensure_home(paths)
    command = [
        sys.executable,
        "-c",
        "from codex_session_delete import cli; import sys; cli.maybe_print_update_notice = lambda: None; raise SystemExit(cli.main(['launch', *sys.argv[1:]]))",
        *normalize_passthrough_args(args),
    ]
    package_root = str(Path(__file__).resolve().parent.parent)
    inherited_pythonpath = os.environ.get("PYTHONPATH")
    env = {
        **os.environ,
        "PYTHONPATH": package_root if not inherited_pythonpath else f"{package_root}{os.pathsep}{inherited_pythonpath}",
    }
    completed = subprocess.run(command, check=False, cwd=command_cwd(paths), env=env)
    return int(completed.returncode)


def print_help_for_topic(parser: argparse.ArgumentParser, topic: str | None) -> int:
    if not topic:
        parser.print_help()
        return 0
    subparsers_action = next(
        (action for action in parser._actions if isinstance(action, argparse._SubParsersAction)),
        None,
    )
    if subparsers_action is None or topic not in subparsers_action.choices:
        print(f"Unknown help topic: {topic}", file=sys.stderr)
        return 1
    subparsers_action.choices[topic].print_help()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) >= 2 and args[0] == "-m" and args[1] == "codex_session_delete":
        return run_bundled_upstream(args[2:])
    if args and args[0] == "bundled-upstream":
        return run_bundled_upstream(args[1:])
    if args and args[0] == "npm-postinstall":
        return run_npm_postinstall()

    parser = build_parser()
    ns = parser.parse_args(args)
    command = ns.command

    if command is None:
        parser.print_help()
        return 0
    if command == "help":
        return print_help_for_topic(parser, ns.topic)
    if command == "install-app":
        return run_install_app(repair=False, from_postinstall=getattr(ns, "from_postinstall", False))
    if command == "repair-app":
        return run_install_app(repair=True, from_postinstall=getattr(ns, "from_postinstall", False))
    if command == "setup":
        print_deprecated_alias("setup", "install-app")
        return run_install_app(repair=False, from_postinstall=getattr(ns, "from_postinstall", False))
    if command == "repair":
        print_deprecated_alias("repair", "repair-app")
        return run_install_app(repair=True, from_postinstall=getattr(ns, "from_postinstall", False))
    if command == "doctor":
        return run_doctor(json_mode=getattr(ns, "json", False))
    if command in ("launch", "run"):
        return run_fast_launch(ns.args)
    if command == "version":
        return print_version()
    parser.print_help()
    return 1
