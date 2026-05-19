from __future__ import annotations

from codex_plus_plus_launcher import doctor, runtime


def test_find_codex_binary_ignores_plain_codex_on_windows(monkeypatch):
    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: r"C:\ProgramFiles\nodejs\codex.CMD" if name == "codex" else None)
    monkeypatch.setattr(doctor, "detect_codex_installation", lambda: runtime.CodexInstallation("missing", None, None, None, False, None))

    assert doctor.find_codex_binary() is None


def test_doctor_report_includes_windows_app_details(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(doctor, "bundled_upstream_version", lambda: "1.0.7")
    monkeypatch.setattr(doctor, "find_host_python", lambda: "python")
    monkeypatch.setattr(doctor, "find_codex_binary", lambda: None)
    monkeypatch.setattr(doctor, "installed_package_version", lambda: "0.1.10")
    monkeypatch.setattr(doctor, "global_command_version", lambda: "0.1.10")
    monkeypatch.setattr(doctor, "legacy_auto_inject_state", lambda: "removed")
    monkeypatch.setattr(doctor, "find_windows_codex_app_dir", lambda: r"C:\Program Files\WindowsApps\OpenAI.Codex_xxx")
    monkeypatch.setattr(
        doctor,
        "load_install_state",
        lambda paths: {
            "mode": "external_launch",
            "app_integration_state": "fallback",
            "restart_required": False,
            "fallback_reason": "msix_installation",
            "shortcut_state": "installed",
            "start_menu_state": "installed",
            "shortcut_target": r"C:\Windows\System32\wscript.exe",
            "shortcut_launcher": r"C:\Users\zjh\AppData\Local\CodexPlusPlusLauncher\assets\launch-codexpp.vbs",
            "shortcut_icon": r"C:\codex-plus-plus.ico",
            "shortcut_icon_state": "repo_asset",
            "expected_launcher_version": "0.1.10",
            "shortcut_binary_version": "0.1.10",
            "legacy_auto_inject_state": "removed",
            "stale_global_binaries": "none",
        },
    )
    monkeypatch.setattr(
        doctor,
        "detect_codex_installation",
        lambda: runtime.CodexInstallation(
            kind="msix",
            app_dir=tmp_path / "Codex" / "app",
            resources_dir=tmp_path / "Codex" / "app" / "resources",
            binary_path=tmp_path / "Codex" / "app" / "Codex.exe",
            writable=False,
            packaged_app_id="OpenAI.Codex_abc!App",
        ),
    )
    paths = type("Paths", (), {"home": tmp_path})()

    report = doctor.doctor_report(paths)

    assert report["package_version"] == "0.1.10"
    assert report["bundled_upstream_version"] == "1.0.7"
    assert report["global_command_version"] == "0.1.10"
    assert report["windows_app_dir"] == r"C:\Program Files\WindowsApps\OpenAI.Codex_xxx"
    assert report["install_mode"] == "external_launch"
    assert report["app_integration_state"] == "fallback"
    assert report["restart_required"] == "no"
    assert report["shortcut_state"] == "installed"
    assert report["start_menu_state"] == "installed"
    assert report["shortcut_target"] == r"C:\Windows\System32\wscript.exe"
    assert report["shortcut_launcher"] == r"C:\Users\zjh\AppData\Local\CodexPlusPlusLauncher\assets\launch-codexpp.vbs"
    assert report["shortcut_icon"] == r"C:\codex-plus-plus.ico"
    assert report["shortcut_icon_state"] == "repo_asset"
    assert report["expected_launcher_version"] == "0.1.10"
    assert report["shortcut_binary_version"] == "0.1.10"
    assert report["stale_global_binaries"] == "none"
    assert report["legacy_auto_inject"] == "removed"
    assert report["windows_app_kind"] == "msix"
