from __future__ import annotations

import builtins
import sys
from pathlib import Path

from codex_plus_plus_launcher import cli
from codex_plus_plus_launcher.runtime import InstallResult


def test_doctor_prints_key_values(monkeypatch, capsys):
    monkeypatch.setattr(cli, "doctor_report", lambda: {"platform": "linux", "install_mode": "external_launch"})

    exit_code = cli.main(["doctor"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "platform=linux" in out
    assert "install_mode=external_launch" in out


def test_install_app_calls_runtime(monkeypatch, tmp_path):
    calls = []
    fake_paths = type("Paths", (), {"home": tmp_path})()
    fake_result = InstallResult(
        mode="native_patch",
        app_integration_state="installed",
        restart_required=False,
        state_dir=tmp_path,
        message="ok",
    )

    monkeypatch.setattr(cli, "runtime_paths", lambda: fake_paths)
    monkeypatch.setattr(cli, "ensure_home", lambda paths: calls.append(("home", paths)))
    monkeypatch.setattr(cli, "cleanup_legacy_windows_auto_inject", lambda: calls.append(("cleanup_legacy",)))
    monkeypatch.setattr(cli, "install_app", lambda paths, repair=False, from_postinstall=False, shortcut_mode="real": calls.append(("install", repair, from_postinstall, shortcut_mode)) or fake_result)

    exit_code = cli.main(["install-app"])

    assert exit_code == 0
    assert calls == [("home", fake_paths), ("cleanup_legacy",), ("install", False, False, "real")]


def test_repair_app_calls_runtime_with_repair(monkeypatch, tmp_path):
    calls = []
    fake_paths = type("Paths", (), {"home": tmp_path})()
    fake_result = InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        fallback_reason="msix_installation",
        message="fallback",
    )

    monkeypatch.setattr(cli, "runtime_paths", lambda: fake_paths)
    monkeypatch.setattr(cli, "ensure_home", lambda paths: calls.append(("home", paths)))
    monkeypatch.setattr(cli, "cleanup_legacy_windows_auto_inject", lambda: calls.append(("cleanup_legacy",)))
    monkeypatch.setattr(cli, "install_app", lambda paths, repair=False, from_postinstall=False, shortcut_mode="real": calls.append(("install", repair, from_postinstall, shortcut_mode)) or fake_result)

    exit_code = cli.main(["repair-app"])

    assert exit_code == 0
    assert calls == [("home", fake_paths), ("cleanup_legacy",), ("install", True, False, "real")]


def test_setup_alias_prints_deprecation_and_installs(monkeypatch, tmp_path, capsys):
    fake_paths = type("Paths", (), {"home": tmp_path})()
    fake_result = InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        message="fallback",
    )

    monkeypatch.setattr(cli, "runtime_paths", lambda: fake_paths)
    monkeypatch.setattr(cli, "ensure_home", lambda _paths: None)
    monkeypatch.setattr(cli, "cleanup_legacy_windows_auto_inject", lambda: None)
    monkeypatch.setattr(cli, "install_app", lambda *args, **kwargs: fake_result)

    exit_code = cli.main(["setup"])

    assert exit_code == 0
    assert "deprecated" in capsys.readouterr().out


def test_npm_postinstall_calls_install_app(monkeypatch, tmp_path):
    calls = []
    fake_paths = type("Paths", (), {"home": tmp_path})()
    fake_result = InstallResult(
        mode="native_patch",
        app_integration_state="installed",
        restart_required=False,
        state_dir=tmp_path,
        message="ok",
    )

    monkeypatch.setattr(cli, "runtime_paths", lambda: fake_paths)
    monkeypatch.setattr(cli, "ensure_home", lambda paths: calls.append(("home", paths)))
    monkeypatch.setattr(cli, "cleanup_legacy_windows_auto_inject", lambda: calls.append(("cleanup_legacy",)))
    monkeypatch.setattr(cli, "install_app", lambda paths, repair=False, from_postinstall=False, shortcut_mode="real": calls.append(("install", repair, from_postinstall, shortcut_mode)) or fake_result)

    exit_code = cli.main(["npm-postinstall"])

    assert exit_code == 0
    assert calls == [("home", fake_paths), ("cleanup_legacy",), ("install", False, True, "real")]


def test_npm_postinstall_can_skip_shortcuts(monkeypatch, tmp_path):
    calls = []
    fake_paths = type("Paths", (), {"home": tmp_path})()
    fake_result = InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        message="ok",
    )

    monkeypatch.setenv("CODEXPP_SHORTCUT_MODE", "skip")
    monkeypatch.setattr(cli, "runtime_paths", lambda: fake_paths)
    monkeypatch.setattr(cli, "ensure_home", lambda paths: calls.append(("home", paths)))
    monkeypatch.setattr(cli, "cleanup_legacy_windows_auto_inject", lambda: calls.append(("cleanup_legacy",)))
    monkeypatch.setattr(cli, "install_app", lambda paths, repair=False, from_postinstall=False, shortcut_mode="real": calls.append(("install", repair, from_postinstall, shortcut_mode)) or fake_result)

    exit_code = cli.main(["npm-postinstall"])

    assert exit_code == 0
    assert calls == [("home", fake_paths), ("cleanup_legacy",), ("install", False, True, "skip")]


def test_binary_accepts_python_module_style_upstream_call(monkeypatch):
    seen = []

    monkeypatch.setattr(cli, "run_bundled_upstream", lambda args: seen.append(args) or 0)

    exit_code = cli.main(["-m", "codex_session_delete", "launch", "--debug-port", "9229"])

    assert exit_code == 0
    assert seen == [["launch", "--debug-port", "9229"]]


def test_run_bundled_upstream_suppresses_update_notice(monkeypatch):
    calls = {}

    class FakeUpstreamCli:
        maybe_print_update_notice = staticmethod(lambda: (_ for _ in ()).throw(AssertionError("not patched")))

        @staticmethod
        def main(args):
            calls["args"] = args
            FakeUpstreamCli.maybe_print_update_notice()
            return 0

    monkeypatch.setitem(sys.modules, "codex_session_delete.cli", FakeUpstreamCli)
    monkeypatch.setitem(sys.modules, "codex_session_delete", type("Pkg", (), {"cli": FakeUpstreamCli}))

    exit_code = cli.run_bundled_upstream(["launch"])

    assert exit_code == 0
    assert calls["args"] == ["launch"]


def test_bare_command_prints_help_without_running_install(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_install_app", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("install should not run")))

    exit_code = cli.main([])

    assert exit_code == 0
    assert "Codex++ launcher wrapper" in capsys.readouterr().out


def test_help_subcommand_prints_top_level_help(capsys):
    exit_code = cli.main(["help"])

    assert exit_code == 0
    assert "install-app" in capsys.readouterr().out


def test_help_subcommand_prints_command_help(capsys):
    exit_code = cli.main(["help", "install-app"])

    assert exit_code == 0
    assert "usage:" in capsys.readouterr().out


def test_help_subcommand_fails_for_unknown_topic(capsys):
    exit_code = cli.main(["help", "missing-command"])

    assert exit_code == 1
    assert "Unknown help topic" in capsys.readouterr().err


def test_launch_uses_fast_launch(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "run_fast_launch", lambda args: seen.append(args) or 0)

    exit_code = cli.main(["launch", "--", "--debug-port", "9229"])

    assert exit_code == 0
    assert seen == [["--", "--debug-port", "9229"]]


def test_run_alias_uses_fast_launch(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "run_fast_launch", lambda args: seen.append(args) or 0)

    exit_code = cli.main(["run", "--", "--debug-port", "9229"])

    assert exit_code == 0
    assert seen == [["--", "--debug-port", "9229"]]


def test_fast_launch_uses_runtime_home_as_cwd(monkeypatch, tmp_path):
    fake_paths = type(
        "Paths",
        (),
        {
            "home": tmp_path,
            "assets_dir": tmp_path / "assets",
            "launcher_log": tmp_path / "launcher.log",
            "state_file": tmp_path / "install-state.json",
            "shortcuts_dir": tmp_path / "shortcuts",
        },
    )()
    seen = {}

    monkeypatch.setattr(cli, "runtime_paths", lambda: fake_paths)
    monkeypatch.setattr(cli, "ensure_home", lambda paths: None)
    monkeypatch.setattr(cli, "cleanup_windows_npm_conflicts", lambda: None)

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["cwd"] = kwargs.get("cwd")
        seen["env"] = kwargs.get("env")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli.run_fast_launch([]) == 0
    assert seen["cwd"] == tmp_path
    assert seen["command"][0:2] == [sys.executable, "-c"]
    assert "maybe_print_update_notice = lambda: None" in seen["command"][2]
    assert str(Path(cli.__file__).resolve().parent.parent) in seen["env"]["PYTHONPATH"]


def test_print_install_result_mentions_launch_fallback(capsys, tmp_path):
    result = InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        fallback_reason="msix_installation",
        message="fallback",
        shortcut_state="installed",
        start_menu_state="installed",
        shortcut_target=tmp_path / "wscript.exe",
        shortcut_launcher=tmp_path / "launch-codexpp.vbs",
        shortcut_icon=tmp_path / "codex-plus-plus.ico",
        shortcut_icon_state="repo_asset",
        legacy_auto_inject_state="removed",
        expected_launcher_version="0.1.10",
        global_command_version="0.1.10",
        shortcut_binary_version="0.1.10",
        stale_global_binaries="none",
    )

    exit_code = cli._print_install_result(result)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Use `cxpp launch`" in out
    assert "fallback_reason=msix_installation" in out
    assert "shortcut_state=installed" in out
    assert "start_menu_state=installed" in out
    assert "legacy_auto_inject=removed" in out
    assert "expected_launcher_version=0.1.10" in out
    assert "global_command_version=0.1.10" in out
    assert "shortcut_binary_version=0.1.10" in out
    assert "stale_global_binaries=none" in out
    assert "shortcut_target=" in out
    assert "shortcut_launcher=" in out
    assert "shortcut_icon=" in out
    assert "shortcut_icon_state=repo_asset" in out


def test_print_install_result_warns_about_command_version_mismatch(capsys, tmp_path):
    result = InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        message="fallback",
        shortcut_state="installed",
        start_menu_state="installed",
        legacy_auto_inject_state="removed",
        expected_launcher_version="0.1.10",
        global_command_version="0.1.5",
    )

    exit_code = cli._print_install_result(result)

    assert exit_code == 0
    assert "Detected a mismatched global cxpp command version" in capsys.readouterr().out


def test_print_install_result_prompts_manual_restart_when_not_interactive(monkeypatch, capsys, tmp_path):
    result = InstallResult(
        mode="native_patch",
        app_integration_state="installed",
        restart_required=True,
        state_dir=tmp_path,
        message="restart needed",
        shortcut_state="installed",
        start_menu_state="installed",
    )
    monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: False)

    exit_code = cli._print_install_result(result)

    assert exit_code == 0
    assert "Please restart Codex App manually" in capsys.readouterr().out


def test_print_install_result_can_restart_interactively(monkeypatch, capsys, tmp_path):
    result = InstallResult(
        mode="native_patch",
        app_integration_state="installed",
        restart_required=True,
        state_dir=tmp_path,
        message="restart needed",
        shortcut_state="installed",
        start_menu_state="installed",
    )
    monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda *_args, **_kwargs: "y")
    monkeypatch.setattr(cli, "detect_codex_installation", lambda: object())
    monkeypatch.setattr(cli, "restart_codex_app", lambda _installation: True)

    exit_code = cli._print_install_result(result)

    assert exit_code == 0
    assert "Codex App was restarted." in capsys.readouterr().out


def test_print_install_result_offers_launch_after_postinstall(monkeypatch, capsys, tmp_path):
    result = InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        message="fallback",
        shortcut_state="installed",
        start_menu_state="installed",
    )
    monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: False)

    exit_code = cli._print_install_result(result, from_postinstall=True)

    assert exit_code == 0
    assert "Run `cxpp launch` or open the Codex++ shortcut" in capsys.readouterr().out
