from __future__ import annotations

import json
from pathlib import Path

from codex_plus_plus_launcher import runtime


def test_runtime_paths_use_codexpp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path))

    paths = runtime.runtime_paths()

    assert paths.home == tmp_path
    assert paths.assets_dir == tmp_path / "assets"
    assert paths.state_file == tmp_path / "install-state.json"


def test_command_cwd_uses_runtime_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path))
    paths = runtime.runtime_paths()

    assert runtime.command_cwd(paths) == tmp_path
    assert paths.assets_dir.is_dir()


def test_record_install_state_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path))
    paths = runtime.runtime_paths()
    result = runtime.InstallResult(
        mode="external_launch",
        app_integration_state="fallback",
        restart_required=False,
        state_dir=tmp_path,
        fallback_reason="msix_installation",
        message="fallback",
        shortcut_state="installed",
        start_menu_state="installed",
        shortcut_target=tmp_path / "cxpp-native.exe",
        shortcut_icon=tmp_path / "codex-plus-plus.ico",
        shortcut_icon_state="installed",
        shortcut_launcher=tmp_path / "launch-codexpp.vbs",
        legacy_auto_inject_state="removed",
        expected_launcher_version="0.1.10",
        global_command_version="0.1.10",
        shortcut_binary_version="0.1.10",
        stale_global_binaries="none",
    )

    runtime.record_install_state(paths, result)
    payload = runtime.load_install_state(paths)

    assert payload["mode"] == "external_launch"
    assert payload["fallback_reason"] == "msix_installation"
    assert payload["shortcut_state"] == "installed"
    assert payload["start_menu_state"] == "installed"
    assert payload["shortcut_icon_state"] == "installed"
    assert payload["shortcut_launcher"] == str(tmp_path / "launch-codexpp.vbs")
    assert payload["legacy_auto_inject_state"] == "removed"
    assert payload["expected_launcher_version"] == "0.1.10"
    assert payload["global_command_version"] == "0.1.10"
    assert payload["shortcut_binary_version"] == "0.1.10"
    assert payload["stale_global_binaries"] == "none"


def test_bundled_icon_bytes_prefers_repo_asset(monkeypatch, tmp_path):
    icon_path = tmp_path / "codex-plus-plus.ico"
    icon_path.write_bytes(b"repo-icon")
    monkeypatch.setattr(runtime, "REPO_ICON_PATH", icon_path)

    icon_bytes, icon_source = runtime._bundled_icon_bytes()

    assert icon_bytes == b"repo-icon"
    assert icon_source == "repo_asset"


def test_deploy_bundled_assets_writes_repo_icon_without_upstream(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path / "state"))
    repo_icon = tmp_path / "repo" / "codex-plus-plus.ico"
    repo_icon.parent.mkdir(parents=True)
    repo_icon.write_bytes(b"repo-icon")
    monkeypatch.setattr(runtime, "REPO_ICON_PATH", repo_icon)
    monkeypatch.setattr(runtime, "_bundled_renderer_text", lambda: None)

    paths = runtime.runtime_paths()
    manifest = runtime.deploy_bundled_assets(paths)

    icon_path = paths.assets_dir / "codex-plus-plus.ico"
    assert icon_path.exists()
    assert icon_path.read_bytes() == b"repo-icon"
    assert manifest["icon_path"] == str(icon_path)
    assert manifest["icon_source"] == "repo_asset"


def test_bundled_upstream_version_prefers_release_metadata(monkeypatch, tmp_path):
    metadata = tmp_path / "upstream-release.json"
    metadata.write_text('{"version": "v1.2.3"}\n', encoding="utf-8")
    monkeypatch.setattr(runtime, "PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(runtime.importlib_resources, "files", lambda _package: (_ for _ in ()).throw(ModuleNotFoundError()))

    assert runtime.bundled_upstream_version() == "v1.2.3"


def test_windows_global_nodejs_dir_prefers_npm_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    npm_cmd = tmp_path / "npm.cmd"
    node_exe = tmp_path / "node.exe"
    npm_prefix = tmp_path / "prefix"
    npm_cmd.write_text("", encoding="utf-8")
    node_exe.write_text("", encoding="utf-8")

    def fake_which(name):
        if name == "npm":
            return str(npm_cmd)
        if name == "node":
            return str(node_exe)
        return None

    def fake_run(*_args, **_kwargs):
        return type("R", (), {"returncode": 0, "stdout": str(npm_prefix), "stderr": ""})()

    monkeypatch.setattr(runtime.shutil, "which", fake_which)
    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    assert runtime.windows_global_nodejs_dir() == npm_prefix


def test_remove_broken_windows_npm_shims_deletes_orphaned_launchers(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    node_dir = tmp_path / "nodejs"
    node_dir.mkdir()
    (node_dir / "node.exe").write_text("", encoding="utf-8")
    for name in ("cxpp.cmd", "cxpp.ps1", "codexpp.cmd"):
        (node_dir / name).write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime.shutil, "which", lambda name: str(node_dir / "node.exe") if name == "node" else None)

    removed = runtime.remove_broken_windows_npm_shims()

    assert {path.name for path in removed} == {"cxpp.cmd", "cxpp.ps1", "codexpp.cmd"}
    assert not (node_dir / "cxpp.cmd").exists()


def test_packaged_app_user_model_id_from_windowsapps_path():
    app_dir = Path("C:/Program Files/WindowsApps/OpenAI.Codex_26.506.2212.0_x64__2p2nqsd0c76g0/app")

    assert runtime.packaged_app_user_model_id(app_dir) == "OpenAI.Codex_2p2nqsd0c76g0!App"


def test_packaged_app_user_model_id_ignores_non_packaged_path():
    app_dir = Path("C:/Codex/app")

    assert runtime.packaged_app_user_model_id(app_dir) is None


def test_detect_codex_installation_returns_missing_when_not_found(monkeypatch):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "find_windows_codex_app_dir", lambda: None)
    monkeypatch.setattr(runtime, "_local_windows_codex_candidates", lambda: [])

    installation = runtime.detect_codex_installation()

    assert installation.kind == "missing"
    assert installation.app_dir is None


def test_detect_codex_installation_marks_msix_as_not_writable(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    app_root = tmp_path / "OpenAI.Codex_26.506.2212.0_x64__2p2nqsd0c76g0"
    app_dir = app_root / "app"
    resources = app_dir / "resources"
    resources.mkdir(parents=True)
    monkeypatch.setattr(runtime, "find_windows_codex_app_dir", lambda: str(app_root))

    installation = runtime.detect_codex_installation()

    assert installation.kind == "msix"
    assert installation.writable is False


def test_install_app_falls_back_for_missing_codex(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path))
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "legacy_auto_inject_state", lambda: "removed")
    monkeypatch.setattr(runtime, "detect_codex_installation", lambda: runtime.CodexInstallation("missing", None, None, None, False, None))
    monkeypatch.setattr(
        runtime,
        "install_windows_shortcuts",
        lambda paths, mode="real": runtime.InstallResult(
            mode="external_launch",
            app_integration_state="unknown",
            restart_required=False,
            state_dir=tmp_path,
            shortcut_state="installed",
            start_menu_state="installed",
            legacy_auto_inject_state="removed",
        ),
    )

    result = runtime.install_app(runtime.runtime_paths())

    assert result.mode == "external_launch"
    assert result.app_integration_state == "missing"
    assert result.fallback_reason == "codex_app_not_found"
    assert result.shortcut_state == "installed"
    assert result.start_menu_state == "installed"
    assert result.legacy_auto_inject_state == "removed"
    assert (tmp_path / "external-launch.txt").exists()


def test_install_app_falls_back_for_msix(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path))
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "legacy_auto_inject_state", lambda: "removed")
    installation = runtime.CodexInstallation(
        kind="msix",
        app_dir=tmp_path / "WindowsApps" / "Codex" / "app",
        resources_dir=tmp_path / "WindowsApps" / "Codex" / "app" / "resources",
        binary_path=None,
        writable=False,
        packaged_app_id="OpenAI.Codex_abc!App",
    )
    monkeypatch.setattr(runtime, "detect_codex_installation", lambda: installation)
    monkeypatch.setattr(
        runtime,
        "install_windows_shortcuts",
        lambda paths, mode="real": runtime.InstallResult(
            mode="external_launch",
            app_integration_state="unknown",
            restart_required=False,
            state_dir=tmp_path,
            shortcut_state="installed",
            start_menu_state="installed",
            legacy_auto_inject_state="removed",
        ),
    )

    result = runtime.install_app(runtime.runtime_paths())

    assert result.mode == "external_launch"
    assert result.app_integration_state == "fallback"
    assert result.fallback_reason == "msix_installation"
    assert result.shortcut_state == "installed"
    assert result.start_menu_state == "installed"
    assert result.legacy_auto_inject_state == "removed"
    assert "WindowsApps" in (tmp_path / "external-launch.txt").read_text(encoding="utf-8")


def test_install_app_uses_native_patch_when_writable(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    app_dir = tmp_path / "Codex" / "app"
    resources = app_dir / "resources"
    resources.mkdir(parents=True)
    installation = runtime.CodexInstallation(
        kind="native",
        app_dir=app_dir,
        resources_dir=resources,
        binary_path=app_dir / "Codex.exe",
        writable=True,
        packaged_app_id=None,
    )
    monkeypatch.setattr(runtime, "detect_codex_installation", lambda: installation)
    monkeypatch.setattr(runtime, "windows_codex_running", lambda: False)
    monkeypatch.setattr(runtime, "deploy_bundled_assets", lambda paths: {"renderer_script": str(paths.assets_dir / "renderer-inject.js"), "icon_path": str(paths.assets_dir / "codex-plus-plus.ico")})
    monkeypatch.setattr(runtime, "install_windows_shortcuts", lambda paths, mode="real": runtime.InstallResult(mode="external_launch", app_integration_state="unknown", restart_required=False, state_dir=tmp_path, shortcut_state="installed", start_menu_state="installed", shortcut_icon_state="installed"))
    copied = []
    monkeypatch.setattr(runtime.shutil, "copy2", lambda src, dest: copied.append((Path(src), Path(dest))))

    result = runtime.install_app(runtime.runtime_paths())

    assert result.mode == "native_patch"
    assert result.app_integration_state == "installed"
    assert result.shortcut_state == "installed"
    assert result.start_menu_state == "installed"
    assert copied
    assert (resources / "codex-plus-plus-launcher" / "integration.json").exists()


def test_install_app_falls_back_when_native_patch_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path / "state"))
    app_dir = tmp_path / "Codex" / "app"
    resources = app_dir / "resources"
    resources.mkdir(parents=True)
    installation = runtime.CodexInstallation(
        kind="native",
        app_dir=app_dir,
        resources_dir=resources,
        binary_path=app_dir / "Codex.exe",
        writable=True,
        packaged_app_id=None,
    )
    monkeypatch.setattr(runtime, "detect_codex_installation", lambda: installation)
    monkeypatch.setattr(runtime, "install_windows_shortcuts", lambda paths, mode="real": runtime.InstallResult(mode="external_launch", app_integration_state="unknown", restart_required=False, state_dir=tmp_path, shortcut_state="installed", start_menu_state="installed"))
    monkeypatch.setattr(runtime, "install_native_patch", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = runtime.install_app(runtime.runtime_paths())

    assert result.mode == "external_launch"
    assert result.fallback_reason == "native_patch_failed"


def test_install_windows_shortcuts_creates_desktop_and_start_menu_entries(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setattr(runtime, "windows_global_binary_path", lambda: tmp_path / "cxpp-native-0.1.5-win32-x64.exe")
    monkeypatch.setattr(runtime, "legacy_auto_inject_state", lambda: "removed")
    monkeypatch.setattr(runtime, "global_command_version", lambda: "0.1.10")
    monkeypatch.setattr(runtime, "remove_outdated_global_binaries", lambda _target: [])
    monkeypatch.setattr(runtime, "describe_stale_global_binaries", lambda _target: "none")
    def fake_deploy(paths):
        icon_path = paths.assets_dir / "codex-plus-plus.ico"
        icon_path.write_bytes(b"repo-icon")
        return {
            "renderer_script": None,
            "icon_path": str(paths.assets_dir / "codex-plus-plus.ico"),
            "icon_source": "repo_asset",
        }

    monkeypatch.setattr(runtime, "deploy_bundled_assets", fake_deploy)
    seen = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    paths = runtime.runtime_paths()
    runtime.ensure_home(paths)

    result = runtime.install_windows_shortcuts(paths)

    assert result.shortcut_state == "installed"
    assert result.start_menu_state == "installed"
    assert result.shortcut_icon_state == "repo_asset"
    assert result.shortcut_target == Path(r"C:\Windows\System32\wscript.exe")
    assert result.shortcut_launcher == paths.assets_dir / "launch-codexpp.vbs"
    assert result.legacy_auto_inject_state == "removed"
    assert result.expected_launcher_version == "1.2.4"
    assert result.global_command_version == "0.1.10"
    assert result.shortcut_binary_version == "0.1.5"
    assert result.stale_global_binaries == "none"
    assert len(seen) == 2
    assert (paths.shortcuts_dir / "desktop-shortcut.txt").exists()
    assert (paths.shortcuts_dir / "start-menu-shortcut.txt").exists()
    assert (paths.assets_dir / "launch-codexpp.vbs").exists()


def test_install_windows_shortcuts_prefers_repo_icon_when_asset_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setattr(runtime, "windows_global_binary_path", lambda: tmp_path / "cxpp-native-0.1.5-win32-x64.exe")
    monkeypatch.setattr(runtime, "legacy_auto_inject_state", lambda: "removed")
    monkeypatch.setattr(runtime, "global_command_version", lambda: "0.1.10")
    monkeypatch.setattr(runtime, "remove_outdated_global_binaries", lambda _target: [])
    monkeypatch.setattr(runtime, "describe_stale_global_binaries", lambda _target: "none")
    seen = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def fake_deploy(paths):
        icon_path = paths.assets_dir / "codex-plus-plus.ico"
        icon_path.write_bytes(b"repo-icon")
        return {"renderer_script": None, "icon_path": str(icon_path), "icon_source": "repo_asset"}

    monkeypatch.setattr(runtime, "deploy_bundled_assets", fake_deploy)
    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    paths = runtime.runtime_paths()
    runtime.ensure_home(paths)

    result = runtime.install_windows_shortcuts(paths)

    assert result.shortcut_icon_state == "repo_asset"
    assert result.shortcut_icon == paths.assets_dir / "codex-plus-plus.ico"
    assert result.shortcut_launcher == paths.assets_dir / "launch-codexpp.vbs"
    assert result.stale_global_binaries == "none"
    assert len(seen) == 2


def test_install_windows_shortcuts_can_skip_real_shortcut_creation(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "windows_global_binary_path", lambda: tmp_path / "cxpp-native-0.1.5-win32-x64.exe")
    monkeypatch.setattr(runtime, "legacy_auto_inject_state", lambda: "removed")
    monkeypatch.setattr(runtime, "global_command_version", lambda: "0.1.10")
    monkeypatch.setattr(runtime, "remove_outdated_global_binaries", lambda _target: [])
    monkeypatch.setattr(runtime, "describe_stale_global_binaries", lambda _target: "none")
    monkeypatch.setattr(runtime, "deploy_bundled_assets", lambda paths: {"renderer_script": None, "icon_path": str(paths.assets_dir / "codex-plus-plus.ico")})
    monkeypatch.setattr(runtime.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not create real shortcut")))
    paths = runtime.runtime_paths()
    runtime.ensure_home(paths)

    result = runtime.install_windows_shortcuts(paths, mode="skip")

    assert result.shortcut_state == "skipped"
    assert result.start_menu_state == "skipped"
    assert result.expected_launcher_version == "1.2.4"
    assert result.stale_global_binaries == "none"


def test_write_windows_launch_script_uses_hidden_window(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXPP_HOME", str(tmp_path))
    paths = runtime.runtime_paths()

    script_path = runtime.write_windows_launch_script(paths, tmp_path / "cxpp-native-0.1.10-win32-x64.exe", "launch")

    content = script_path.read_text(encoding="utf-8")
    assert "shell.Run" in content
    assert ", 0, False" in content
    assert "launch" in content


def test_legacy_auto_inject_state_returns_removed_on_non_windows(monkeypatch):
    monkeypatch.setattr(runtime.sys, "platform", "linux")

    assert runtime.legacy_auto_inject_state() == "unsupported"


def test_remove_outdated_global_binaries_keeps_current_version(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    current = prefix / "cxpp-native-0.1.10-win32-x64.exe"
    legacy = prefix / "cxpp-native-0.1.5-win32-x64.exe"
    current.write_text("", encoding="utf-8")
    legacy.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime, "windows_global_nodejs_dir", lambda: prefix)
    monkeypatch.setattr(runtime, "installed_command_dir", lambda _name="cxpp": None)

    removed = runtime.remove_outdated_global_binaries(current)

    assert removed == [legacy]
    assert current.exists()
    assert not legacy.exists()


def test_describe_stale_global_binaries_reports_none_when_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    current = tmp_path / "cxpp-native-0.1.10-win32-x64.exe"
    current.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime, "windows_global_nodejs_dir", lambda: tmp_path)
    monkeypatch.setattr(runtime, "installed_command_dir", lambda _name="cxpp": None)

    assert runtime.describe_stale_global_binaries(current) == "none"


def test_describe_stale_global_binaries_lists_legacy_versions(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    current = tmp_path / "cxpp-native-0.1.10-win32-x64.exe"
    legacy = tmp_path / "cxpp-native-0.1.6-win32-x64.exe"
    current.write_text("", encoding="utf-8")
    legacy.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime, "windows_global_nodejs_dir", lambda: tmp_path)
    monkeypatch.setattr(runtime, "installed_command_dir", lambda _name="cxpp": None)

    assert runtime.describe_stale_global_binaries(current) == legacy.name


def test_cleanup_legacy_windows_auto_inject_removes_disabled_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    disabled_flag = tmp_path / "watcher.disabled"
    disabled_flag.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime, "legacy_watch_disabled_flag", lambda: disabled_flag)
    monkeypatch.setattr(runtime.subprocess, "run", lambda *_args, **_kwargs: type("R", (), {"returncode": 0})())

    runtime.cleanup_legacy_windows_auto_inject()

    assert not disabled_flag.exists()


def test_start_codex_app_uses_packaged_activation(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    installation = runtime.CodexInstallation(
        kind="msix",
        app_dir=tmp_path / "app",
        resources_dir=None,
        binary_path=None,
        writable=False,
        packaged_app_id="OpenAI.Codex_abc!App",
    )
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    assert runtime.start_codex_app(installation) is True
    assert seen["command"] == ["explorer.exe", "shell:AppsFolder\\OpenAI.Codex_abc!App"]


def test_restart_codex_app_stops_then_starts(monkeypatch, tmp_path):
    installation = runtime.CodexInstallation(
        kind="native",
        app_dir=tmp_path / "app",
        resources_dir=None,
        binary_path=tmp_path / "app" / "Codex.exe",
        writable=True,
        packaged_app_id=None,
    )
    calls = []
    monkeypatch.setattr(runtime, "stop_codex_app", lambda: calls.append("stop") or True)
    monkeypatch.setattr(runtime, "start_codex_app", lambda _installation: calls.append("start") or True)
    monkeypatch.setattr(runtime.time, "sleep", lambda _seconds: None)

    assert runtime.restart_codex_app(installation) is True
    assert calls == ["stop", "start"]
