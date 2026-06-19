from __future__ import annotations

import shutil
import sys

from codex_plus_plus_launcher.runtime import (
    RuntimePaths,
    bundled_upstream_version,
    detect_codex_installation,
    find_host_python,
    find_windows_codex_app_dir,
    global_command_version,
    installed_package_version,
    legacy_auto_inject_state,
    load_install_state,
    runtime_paths,
    shortcut_sidecar_install_root,
    shortcut_sidecar_version,
)


def find_codex_binary() -> str | None:
    candidates = ("codex-desktop", "openai-codex-desktop")
    if sys.platform != "win32":
        candidates = ("codex-desktop", "codex", "openai-codex-desktop")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    installation = detect_codex_installation()
    if installation.binary_path is not None:
        return str(installation.binary_path)
    return None


def _sidecar_drift_value(installed: str | None, bundled: str | None) -> str:
    """Compute the sidecar_drift status surfaced by doctor.

    - "none": both versions are known and equal
    - "mismatch:installed=X,bundled=Y": both known but different
    - "unknown": either version is missing (older install / preflight running
      from source tree without bundled sidecar)
    """
    if not installed or not bundled:
        return "unknown"
    if installed == bundled:
        return "none"
    return f"mismatch:installed={installed},bundled={bundled}"


def doctor_report(paths: RuntimePaths | None = None) -> dict[str, str]:
    resolved_paths = paths or runtime_paths()
    installation = detect_codex_installation()
    state = load_install_state(resolved_paths)

    bundled_version = bundled_upstream_version()
    installed_sidecar_version = shortcut_sidecar_version()
    sidecar_root = shortcut_sidecar_install_root()

    report = {
        "platform": sys.platform,
        "package_version": installed_package_version(),
        "bundled_upstream_version": bundled_version or "missing",
        "global_command_version": global_command_version() or "missing",
        "host_python": find_host_python() or "missing",
        "codex_binary": find_codex_binary() or "missing",
        "state_dir": str(resolved_paths.home),
        "install_mode": str(state.get("mode") or ("external_launch" if installation.kind == "msix" else "missing")),
        "app_integration_state": str(state.get("app_integration_state") or ("unsupported" if installation.kind == "missing" else "missing")),
        "restart_required": "yes" if bool(state.get("restart_required")) else "no",
        "shortcut_state": str(state.get("shortcut_state") or "missing"),
        "start_menu_state": str(state.get("start_menu_state") or "missing"),
        "legacy_auto_inject": str(state.get("legacy_auto_inject_state") or legacy_auto_inject_state()),
        "shortcut_sidecar_root": str(sidecar_root) if sidecar_root is not None else "missing",
        "shortcut_sidecar_version": installed_sidecar_version or "unknown",
        "sidecar_drift": _sidecar_drift_value(installed_sidecar_version, bundled_version),
    }
    if sys.platform == "win32":
        report["windows_app_dir"] = find_windows_codex_app_dir() or "missing"
        report["windows_app_kind"] = installation.kind
    if installation.app_dir is not None:
        report["app_dir"] = str(installation.app_dir)
    if installation.resources_dir is not None:
        report["resources_dir"] = str(installation.resources_dir)
    if installation.binary_path is not None:
        report["app_binary"] = str(installation.binary_path)
    if state.get("fallback_reason"):
        report["fallback_reason"] = str(state["fallback_reason"])
    if state.get("shortcut_target"):
        report["shortcut_target"] = str(state["shortcut_target"])
    if state.get("shortcut_launcher"):
        report["shortcut_launcher"] = str(state["shortcut_launcher"])
    if state.get("shortcut_icon"):
        report["shortcut_icon"] = str(state["shortcut_icon"])
    if state.get("shortcut_icon_state"):
        report["shortcut_icon_state"] = str(state["shortcut_icon_state"])
    if state.get("expected_launcher_version"):
        report["expected_launcher_version"] = str(state["expected_launcher_version"])
    if state.get("shortcut_binary_version"):
        report["shortcut_binary_version"] = str(state["shortcut_binary_version"])
    if state.get("stale_global_binaries"):
        report["stale_global_binaries"] = str(state["stale_global_binaries"])
    return report
