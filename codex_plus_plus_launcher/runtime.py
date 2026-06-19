from __future__ import annotations

import importlib.resources as importlib_resources
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

from codex_plus_plus_launcher import __version__


WINDOWS_COMMAND_NAMES = ("cxpp", "codexpp", "codex-plus-plus-launcher")
LEGACY_WATCHER_RUN_KEY = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
LEGACY_WATCHER_RUN_NAME = "CodexPlusPlusWatcher"
LEGACY_WATCHER_SHORTCUT_NAME = "CodexPlusPlusWatcher.lnk"
WINDOWS_PACKAGE_RE = re.compile(r"OpenAI\.Codex_[^\\]+__([a-z0-9]+)", re.IGNORECASE)
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ICON_PATH = PACKAGE_ROOT / "assets" / "codex-plus-plus.ico"
LAUNCH_VBS_NAME = "launch-codexpp.vbs"
UPSTREAM_RELEASE_METADATA_NAME = "upstream-release.json"


@dataclass(frozen=True)
class RuntimePaths:
    home: Path
    assets_dir: Path
    launcher_log: Path
    state_file: Path
    shortcuts_dir: Path


@dataclass(frozen=True)
class CodexInstallation:
    kind: str
    app_dir: Path | None
    resources_dir: Path | None
    binary_path: Path | None
    writable: bool
    packaged_app_id: str | None


@dataclass(frozen=True)
class InstallResult:
    mode: str
    app_integration_state: str
    restart_required: bool
    state_dir: Path
    app_dir: Path | None = None
    codex_binary: Path | None = None
    fallback_reason: str | None = None
    message: str = ""
    shortcut_state: str = "missing"
    start_menu_state: str = "missing"
    shortcut_target: Path | None = None
    shortcut_icon: Path | None = None
    shortcut_icon_state: str = "missing"
    shortcut_launcher: Path | None = None
    legacy_auto_inject_state: str = "unknown"
    expected_launcher_version: str | None = None
    global_command_version: str | None = None
    shortcut_binary_version: str | None = None
    stale_global_binaries: str = "unknown"
    launched: bool = False

    @property
    def succeeded(self) -> bool:
        return self.app_integration_state in {"installed", "fallback"}


def app_home() -> Path:
    base = os.environ.get("CODEXPP_HOME")
    if base:
        return Path(base).expanduser()
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "CodexPlusPlusLauncher"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "CodexPlusPlusLauncher"
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        return Path(state_home) / "codex-plus-plus-launcher"
    return Path.home() / ".codex-plus-plus-launcher"


def runtime_paths() -> RuntimePaths:
    home = app_home()
    return RuntimePaths(
        home=home,
        assets_dir=home / "assets",
        launcher_log=home / "launcher.log",
        state_file=home / "install-state.json",
        shortcuts_dir=home / "shortcuts",
    )


def ensure_home(paths: RuntimePaths) -> None:
    paths.assets_dir.mkdir(parents=True, exist_ok=True)
    paths.shortcuts_dir.mkdir(parents=True, exist_ok=True)


def command_cwd(paths: RuntimePaths) -> Path:
    ensure_home(paths)
    return paths.home


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def installed_command_dir(command_name: str = "cxpp") -> Path | None:
    resolved = shutil.which(command_name)
    if resolved:
        return Path(resolved).resolve().parent
    for candidate_dir in [Path(sys.executable).resolve().parent]:
        for extension in (".exe", ".cmd", ".bat", ""):
            candidate = candidate_dir / f"{command_name}{extension}"
            if candidate.exists():
                return candidate_dir
    return None


def windows_global_nodejs_dir() -> Path | None:
    if sys.platform != "win32":
        return None
    prefix_override = os.environ.get("npm_config_prefix")
    if prefix_override:
        return Path(prefix_override)
    npm = shutil.which("npm")
    if npm:
        try:
            result = subprocess.run(
                [npm, "prefix", "-g"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result and result.returncode == 0:
            prefix = result.stdout.strip()
            if prefix:
                return Path(prefix)
    node = shutil.which("node")
    if not node:
        return None
    return Path(node).resolve().parent


def remove_broken_windows_npm_shims() -> list[Path]:
    if sys.platform != "win32":
        return []

    removed: list[Path] = []
    node_dir = windows_global_nodejs_dir()
    if node_dir is None:
        return removed

    package_root = node_dir / "node_modules" / "@duanluan" / "codex-plus-plus-launcher"
    package_missing = not package_root.exists()

    for command_name in WINDOWS_COMMAND_NAMES:
        for suffix in ("", ".cmd", ".ps1"):
            candidate = node_dir / f"{command_name}{suffix}"
            if candidate.exists() and package_missing:
                try:
                    candidate.unlink()
                    removed.append(candidate)
                except OSError:
                    continue

    if package_missing:
        scoped_dir = node_dir / "node_modules" / "@duanluan"
        try:
            if scoped_dir.exists() and not any(scoped_dir.iterdir()):
                scoped_dir.rmdir()
        except OSError:
            pass

    return removed


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _serialize_path(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _deserialize_path(value: object) -> Path | None:
    if isinstance(value, str) and value:
        return Path(value)
    return None


def load_install_state(paths: RuntimePaths) -> dict[str, Any]:
    if not paths.state_file.exists():
        return {}
    try:
        payload = json.loads(paths.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def record_install_state(paths: RuntimePaths, result: InstallResult) -> None:
    ensure_home(paths)
    payload = {
        "mode": result.mode,
        "app_integration_state": result.app_integration_state,
        "restart_required": result.restart_required,
        "state_dir": str(result.state_dir),
        "app_dir": _serialize_path(result.app_dir),
        "codex_binary": _serialize_path(result.codex_binary),
        "fallback_reason": result.fallback_reason,
        "message": result.message,
        "shortcut_state": result.shortcut_state,
        "start_menu_state": result.start_menu_state,
        "shortcut_target": _serialize_path(result.shortcut_target),
        "shortcut_icon": _serialize_path(result.shortcut_icon),
        "shortcut_icon_state": result.shortcut_icon_state,
        "shortcut_launcher": _serialize_path(result.shortcut_launcher),
        "legacy_auto_inject_state": result.legacy_auto_inject_state,
        "expected_launcher_version": result.expected_launcher_version,
        "global_command_version": result.global_command_version,
        "shortcut_binary_version": result.shortcut_binary_version,
        "stale_global_binaries": result.stale_global_binaries,
        "launched": result.launched,
        "updated_at": _now_iso(),
    }
    paths.state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def legacy_watch_disabled_flag() -> Path:
    return Path.home() / ".codex-session-delete" / "watcher.disabled"


def cleanup_legacy_windows_auto_inject() -> None:
    if sys.platform != "win32":
        return
    flag = legacy_watch_disabled_flag()
    try:
        if flag.exists():
            flag.unlink()
    except OSError:
        pass

    script = f"""
Remove-ItemProperty -Path '{LEGACY_WATCHER_RUN_KEY}' -Name '{LEGACY_WATCHER_RUN_NAME}' -ErrorAction SilentlyContinue | Out-Null
$Startup = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $Startup {ps_quote(LEGACY_WATCHER_SHORTCUT_NAME)}
if (Test-Path $ShortcutPath) {{ Remove-Item $ShortcutPath -Force -ErrorAction SilentlyContinue }}
Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -match 'codex_session_delete\\s+watch|bundled-upstream\\s+watch' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
""".strip()
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            cwd=str(Path.home()),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return


def legacy_auto_inject_state() -> str:
    if sys.platform != "win32":
        return "unsupported"

    script = f"""
$RunValue = (Get-ItemProperty -Path '{LEGACY_WATCHER_RUN_KEY}' -Name '{LEGACY_WATCHER_RUN_NAME}' -ErrorAction SilentlyContinue).{LEGACY_WATCHER_RUN_NAME}
$Startup = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $Startup {ps_quote(LEGACY_WATCHER_SHORTCUT_NAME)}
$DisabledFlag = {ps_quote(str(legacy_watch_disabled_flag()))}
$Watcher = Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -match 'codex_session_delete\\s+watch|bundled-upstream\\s+watch' }} | Select-Object -First 1
$States = @()
if ($RunValue) {{ $States += 'run_key' }}
if (Test-Path $ShortcutPath) {{ $States += 'startup_shortcut' }}
if (Test-Path $DisabledFlag) {{ $States += 'disabled_flag' }}
if ($null -ne $Watcher) {{ $States += 'watcher_running' }}
if ($States.Count -eq 0) {{ 'removed' }} else {{ $States -join ',' }}
""".strip()
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            cwd=str(Path.home()),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    state = result.stdout.strip()
    return state or "removed"


def find_host_python() -> str | None:
    override = os.environ.get("CODEXPP_PYTHON")
    if override:
        return override
    for candidate in ("python3", "python", "py"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def find_windows_codex_app_dir() -> str | None:
    if sys.platform != "win32":
        return None
    command = 'Get-AppxPackage -Name "OpenAI.Codex" | Select-Object -ExpandProperty InstallLocation'
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def packaged_app_user_model_id(app_dir: Path) -> str | None:
    text = str(app_dir).replace("/", "\\")
    match = WINDOWS_PACKAGE_RE.search(text)
    if not match:
        return None
    return f"OpenAI.Codex_{match.group(1)}!App"


def _normalize_windows_app_dir(path: Path) -> Path:
    if path.name.lower() == "app":
        return path
    app_dir = path / "app"
    return app_dir if app_dir.is_dir() else path


def _resolve_windows_binary(app_dir: Path) -> Path | None:
    candidates = (
        app_dir / "Codex.exe",
        app_dir / "codex.exe",
        app_dir.parent / "Codex.exe",
        app_dir.parent / "codex.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resources_dir(app_dir: Path) -> Path | None:
    for candidate in (app_dir / "resources", app_dir / "Resources"):
        if candidate.is_dir():
            return candidate
    return None


def _path_is_writable(directory: Path | None) -> bool:
    if directory is None or not directory.exists():
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix="cxpp-write-", delete=False) as handle:
            probe = Path(handle.name)
        probe.unlink()
        return True
    except OSError:
        return False


def _local_windows_codex_candidates() -> list[Path]:
    local = Path.home() / "AppData" / "Local"
    return [
        local / "Programs" / "Codex",
        local / "Programs" / "Codex" / "app",
    ]


def detect_codex_installation() -> CodexInstallation:
    if sys.platform != "win32":
        binary = shutil.which("codex-desktop") or shutil.which("codex") or shutil.which("openai-codex-desktop")
        binary_path = Path(binary) if binary else None
        app_dir = binary_path.parent if binary_path else None
        resources_dir = app_dir if app_dir and app_dir.is_dir() else None
        return CodexInstallation(
            kind="native" if app_dir else "missing",
            app_dir=app_dir,
            resources_dir=resources_dir,
            binary_path=binary_path,
            writable=_path_is_writable(resources_dir),
            packaged_app_id=None,
        )

    app_dir_text = find_windows_codex_app_dir()
    candidate_path = Path(app_dir_text) if app_dir_text else None
    if candidate_path is None:
        for candidate in _local_windows_codex_candidates():
            if candidate.exists():
                candidate_path = candidate
                break

    if candidate_path is None:
        return CodexInstallation(
            kind="missing",
            app_dir=None,
            resources_dir=None,
            binary_path=None,
            writable=False,
            packaged_app_id=None,
        )

    app_dir = _normalize_windows_app_dir(candidate_path)
    resources_dir = _resources_dir(app_dir)
    packaged_app_id = packaged_app_user_model_id(app_dir)
    kind = "msix" if packaged_app_id else "native"
    writable = False if kind == "msix" else _path_is_writable(resources_dir or app_dir)
    return CodexInstallation(
        kind=kind,
        app_dir=app_dir,
        resources_dir=resources_dir,
        binary_path=_resolve_windows_binary(app_dir),
        writable=writable,
        packaged_app_id=packaged_app_id,
    )


def windows_codex_running() -> bool:
    if sys.platform != "win32":
        return False
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            cwd=str(Path.home()),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(result.stdout.strip())


def _bundled_renderer_text() -> str | None:
    try:
        resource = importlib_resources.files("codex_session_delete").joinpath("inject").joinpath("renderer-inject.js")
        return resource.read_text(encoding="utf-8")
    except Exception:
        return None


def _bundled_icon_bytes() -> tuple[bytes | None, str]:
    if REPO_ICON_PATH.is_file():
        try:
            return REPO_ICON_PATH.read_bytes(), "repo_asset"
        except OSError:
            pass
    try:
        resource = importlib_resources.files("codex_session_delete").joinpath("assets").joinpath("codex-plus-plus.ico")
        return resource.read_bytes(), "upstream_bundle"
    except Exception:
        return None, "missing"


def deploy_bundled_assets(paths: RuntimePaths) -> dict[str, str | None]:
    ensure_home(paths)
    renderer_path = paths.assets_dir / "renderer-inject.js"
    renderer_text = _bundled_renderer_text()
    if renderer_text is not None:
        renderer_path.write_text(renderer_text, encoding="utf-8")
    manifest = {
        "renderer_script": str(renderer_path) if renderer_path.exists() else None,
        "icon_path": None,
        "generated_at": _now_iso(),
        "source": "bundled",
        "icon_source": "missing",
    }
    icon_bytes, icon_source = _bundled_icon_bytes()
    if icon_bytes is not None:
        icon_path = paths.assets_dir / "codex-plus-plus.ico"
        icon_path.write_bytes(icon_bytes)
        manifest["icon_path"] = str(icon_path)
    manifest["icon_source"] = icon_source
    (paths.assets_dir / "payload.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def write_windows_launch_script(paths: RuntimePaths, target: Path, arguments: str) -> Path:
    ensure_home(paths)
    script_path = paths.assets_dir / LAUNCH_VBS_NAME
    command = subprocess.list2cmdline([str(target), *([arguments] if arguments else [])]).strip()
    contents = (
        'Set shell = CreateObject("WScript.Shell")\r\n'
        f'shell.CurrentDirectory = "{str(paths.home).replace(chr(92), chr(92) * 2)}"\r\n'
        f'shell.Run "{command.replace(chr(34), chr(34) * 2)}", 0, False\r\n'
    )
    script_path.write_text(contents, encoding="utf-8")
    return script_path


def installed_package_version() -> str:
    return __version__


def bundled_upstream_version() -> str | None:
    metadata_version = bundled_upstream_release_version()
    if metadata_version:
        return metadata_version
    try:
        import codex_session_delete
    except Exception:
        return None
    version = getattr(codex_session_delete, "__version__", None)
    return version if isinstance(version, str) and version else None


def bundled_upstream_release_version() -> str | None:
    candidates: list[Any] = []
    try:
        candidates.append(importlib_resources.files(__package__).joinpath(UPSTREAM_RELEASE_METADATA_NAME))
    except (AttributeError, ModuleNotFoundError, TypeError, ValueError):
        pass
    candidates.append(PACKAGE_ROOT / UPSTREAM_RELEASE_METADATA_NAME)

    for candidate in candidates:
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, FileNotFoundError, json.JSONDecodeError):
            continue
        version = payload.get("version")
        if isinstance(version, str) and version:
            return version
    return None


def global_command_version(command_name: str = "cxpp") -> str | None:
    candidate_dirs: list[Path] = []
    for candidate in filter(None, [windows_global_nodejs_dir(), installed_command_dir(command_name)]):
        if candidate not in candidate_dirs:
            candidate_dirs.append(candidate)

    for command_dir in candidate_dirs:
        package_json = command_dir / "node_modules" / "@duanluan" / "codex-plus-plus-launcher" / "package.json"
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version = payload.get("version")
        if isinstance(version, str) and version:
            return version
    return None


def binary_version_from_path(path: Path | None) -> str | None:
    if path is None:
        return None
    match = re.search(r"cxpp-native-([0-9][^-]*)-", path.name, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


SIDECAR_VERSION_STAMP_NAME = ".codexpp-sidecar-version"


def shortcut_sidecar_install_root() -> Path | None:
    """Return the directory where the npm postinstall copied the sidecar.

    Mirrors `installSidecarRoot` in npm/launcher.js. Used by doctor() to read
    the stamp file written alongside the sidecar binary.
    """
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return None
        return Path(local) / "Programs" / "Codex++"
    if sys.platform == "darwin":
        primary = Path("/Applications")
        if (primary / SIDECAR_VERSION_STAMP_NAME).is_file() or (primary / "codex-plus-plus").is_file():
            return primary
        fallback = Path.home() / "Applications"
        if (fallback / SIDECAR_VERSION_STAMP_NAME).is_file() or (fallback / "codex-plus-plus").is_file():
            return fallback
        return primary
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / "Codex++"


def shortcut_sidecar_binary(root: Path | None = None) -> Path | None:
    base = root if root is not None else shortcut_sidecar_install_root()
    if base is None:
        return None
    name = "codex-plus-plus.exe" if sys.platform == "win32" else "codex-plus-plus"
    candidate = base / name
    return candidate if candidate.is_file() else None


def _read_sidecar_version_stamp(root: Path) -> str | None:
    stamp = root / SIDECAR_VERSION_STAMP_NAME
    try:
        text = stamp.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    value = text.strip()
    return value or None


def _read_pe_file_version(path: Path) -> str | None:
    """Windows-only fallback: read FileVersion from the PE VS_FIXEDFILEINFO block.

    Used when an older npm install root predates the stamp file. No new
    dependencies — calls into version.dll via ctypes.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None
    try:
        version_dll = ctypes.WinDLL("version", use_last_error=True)
    except OSError:
        return None
    target = str(path)
    try:
        size = version_dll.GetFileVersionInfoSizeW(target, None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version_dll.GetFileVersionInfoW(target, 0, size, buffer):
            return None
        block_ptr = ctypes.c_void_p()
        block_size = wintypes.UINT()
        if not version_dll.VerQueryValueW(buffer, "\\", ctypes.byref(block_ptr), ctypes.byref(block_size)):
            return None
        if block_size.value < 16:
            return None
        raw = ctypes.string_at(block_ptr, block_size.value)
        ms = int.from_bytes(raw[8:12], "little")
        ls = int.from_bytes(raw[12:16], "little")
    except Exception:
        return None
    parts = [ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return ".".join(str(part) for part in parts) or None


def shortcut_sidecar_version() -> str | None:
    """Return the version of the installed sidecar copy, or None when unknown.

    Prefers a stamp file written by npm postinstall (cross-platform). Falls
    back to the PE VersionInfo on Windows for installs that predate the stamp.
    """
    root = shortcut_sidecar_install_root()
    if root is None:
        return None
    stamp_version = _read_sidecar_version_stamp(root)
    if stamp_version:
        return stamp_version
    if sys.platform == "win32":
        binary = shortcut_sidecar_binary(root)
        if binary is not None:
            return _read_pe_file_version(binary)
    return None


def global_binary_candidate_dirs(current_binary: Path | None = None) -> list[Path]:
    candidate_dirs: list[Path] = []
    if current_binary is not None:
        candidate_dirs.append(current_binary.resolve().parent)
    for candidate in filter(None, [windows_global_nodejs_dir(), installed_command_dir("cxpp")]):
        if candidate not in candidate_dirs:
            candidate_dirs.append(candidate)
    return candidate_dirs


def list_stale_global_binaries(current_binary: Path | None) -> list[Path]:
    if sys.platform != "win32":
        return []
    current_binary = current_binary.resolve() if current_binary is not None else None
    stale: list[Path] = []
    for candidate_dir in global_binary_candidate_dirs(current_binary):
        for binary in sorted(candidate_dir.glob("cxpp-native-*-win32-x64.exe")):
            try:
                resolved = binary.resolve()
            except OSError:
                resolved = binary
            if current_binary is not None and resolved == current_binary:
                continue
            stale.append(binary)
    unique: list[Path] = []
    seen: set[str] = set()
    for binary in stale:
        key = str(binary).lower()
        if key not in seen:
            seen.add(key)
            unique.append(binary)
    return unique


def describe_stale_global_binaries(current_binary: Path | None) -> str:
    stale = list_stale_global_binaries(current_binary)
    if not stale:
        return "none"
    return ",".join(path.name for path in stale)


def remove_outdated_global_binaries(current_binary: Path | None) -> list[Path]:
    if sys.platform != "win32":
        return []
    removed: list[Path] = []
    for binary in list_stale_global_binaries(current_binary):
        try:
            binary.unlink()
            removed.append(binary)
        except OSError:
            continue
    return removed


def windows_global_binary_path() -> Path | None:
    if sys.platform != "win32":
        return None
    current_executable = Path(sys.executable)
    if getattr(sys, "frozen", False) and current_executable.name.lower().startswith("cxpp-native-") and current_executable.suffix.lower() == ".exe":
        return current_executable
    override = os.environ.get("CODEXPP_GLOBAL_BINARY")
    if override:
        return Path(override)
    for candidate_dir in filter(None, [installed_command_dir("cxpp"), windows_global_nodejs_dir()]):
        matches = sorted(candidate_dir.glob("cxpp-native-*-win32-x64.exe"))
        if matches:
            return matches[-1]
    return None


def _windows_shortcut_script(
    target: Path,
    arguments: str,
    link_path: Path,
    working_directory: Path,
    description: str,
    icon_location: str | None,
) -> str:
    icon_line = f"$Shortcut.IconLocation = {ps_quote(icon_location)}" if icon_location else ""
    return f"""
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut({ps_quote(str(link_path))})
$Shortcut.TargetPath = {ps_quote(str(target))}
$Shortcut.Arguments = {ps_quote(arguments)}
$Shortcut.WorkingDirectory = {ps_quote(str(working_directory))}
$Shortcut.Description = {ps_quote(description)}
{icon_line}
$Shortcut.Save()
""".strip()


def install_windows_shortcuts(paths: RuntimePaths, mode: str = "real") -> InstallResult:
    if sys.platform != "win32":
        return InstallResult(
            mode="external_launch",
            app_integration_state="unknown",
            restart_required=False,
            state_dir=paths.home,
            shortcut_state="unsupported",
            start_menu_state="unsupported",
        )

    target = windows_global_binary_path()
    if target is None:
        return InstallResult(
            mode="external_launch",
            app_integration_state="unknown",
            restart_required=False,
            state_dir=paths.home,
            shortcut_state="missing",
            start_menu_state="missing",
        )

    remove_outdated_global_binaries(target)

    payload = deploy_bundled_assets(paths)
    expected_version = installed_package_version()
    command_version = global_command_version()
    icon_path_value = payload.get("icon_path")
    icon_path = Path(icon_path_value) if isinstance(icon_path_value, str) and icon_path_value else None
    if icon_path is not None and icon_path.exists():
        icon_location = f"{icon_path},0"
        icon_state = "repo_asset" if payload.get("icon_source") == "repo_asset" else "installed"
    else:
        icon_location = f"{target},0"
        icon_state = "binary_fallback"
    shortcut_binary_version = binary_version_from_path(target)

    if mode == "skip":
        return InstallResult(
            mode="external_launch",
            app_integration_state="unknown",
            restart_required=False,
            state_dir=paths.home,
            shortcut_state="skipped",
            start_menu_state="skipped",
            shortcut_target=target,
            shortcut_icon=icon_path if icon_path is not None and icon_path.exists() else target,
            shortcut_icon_state=icon_state,
            legacy_auto_inject_state=legacy_auto_inject_state(),
            expected_launcher_version=expected_version,
            global_command_version=command_version,
            shortcut_binary_version=shortcut_binary_version,
            stale_global_binaries=describe_stale_global_binaries(target),
        )

    launcher_script = write_windows_launch_script(paths, target, "launch")
    desktop_dir = Path.home() / "Desktop"
    start_menu_dir = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    desktop_link = desktop_dir / "Codex++.lnk"
    start_menu_link = start_menu_dir / "Codex++.lnk"
    shortcut_target = Path(str(PureWindowsPath(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"))
    arguments = f'"{launcher_script}"'
    working_directory = paths.home
    description = "Launch Codex++"

    for parent in (desktop_dir, start_menu_dir):
        parent.mkdir(parents=True, exist_ok=True)

    for link_path in (desktop_link, start_menu_link):
        script = _windows_shortcut_script(shortcut_target, arguments, link_path, working_directory, description, icon_location)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(paths.home),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"failed to create shortcut: {link_path}")

    (paths.shortcuts_dir / "desktop-shortcut.txt").write_text(str(desktop_link) + "\n", encoding="utf-8")
    (paths.shortcuts_dir / "start-menu-shortcut.txt").write_text(str(start_menu_link) + "\n", encoding="utf-8")
    return InstallResult(
        mode="external_launch",
        app_integration_state="unknown",
        restart_required=False,
        state_dir=paths.home,
        shortcut_state="installed",
        start_menu_state="installed",
        shortcut_target=shortcut_target,
        shortcut_icon=icon_path if icon_path is not None and icon_path.exists() else target,
        shortcut_icon_state=icon_state,
        shortcut_launcher=launcher_script,
        legacy_auto_inject_state=legacy_auto_inject_state(),
        expected_launcher_version=expected_version,
        global_command_version=command_version,
        shortcut_binary_version=shortcut_binary_version,
        stale_global_binaries=describe_stale_global_binaries(target),
    )


def _native_patch_directory(installation: CodexInstallation) -> Path:
    if installation.resources_dir is None:
        raise RuntimeError("Codex App resources directory not found")
    return installation.resources_dir / "codex-plus-plus-launcher"


def install_native_patch(installation: CodexInstallation, paths: RuntimePaths) -> Path:
    payload = deploy_bundled_assets(paths)
    target_dir = _native_patch_directory(installation)
    target_dir.mkdir(parents=True, exist_ok=True)

    renderer_script = payload.get("renderer_script")
    if isinstance(renderer_script, str) and renderer_script:
        shutil.copy2(Path(renderer_script), target_dir / "renderer-inject.js")

    integration = {
        "mode": "native_patch",
        "source_state_dir": str(paths.home),
        "app_dir": _serialize_path(installation.app_dir),
        "resources_dir": _serialize_path(installation.resources_dir),
        "installed_at": _now_iso(),
    }
    (target_dir / "integration.json").write_text(json.dumps(integration, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target_dir


def install_external_launch_assets(paths: RuntimePaths, installation: CodexInstallation) -> None:
    payload = deploy_bundled_assets(paths)
    readme = paths.home / "external-launch.txt"
    lines = [
        "Codex++ external launch fallback is active.",
        "Use `cxpp launch` to start Codex++ explicitly.",
    ]
    if installation.kind == "msix":
        lines.append("Detected Microsoft Store / MSIX Codex App, so WindowsApps was not modified.")
    if payload.get("renderer_script"):
        lines.append(f"Bundled renderer asset: {payload['renderer_script']}")
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fallback_result(
    paths: RuntimePaths,
    installation: CodexInstallation,
    reason: str,
    message: str,
    shortcut_state: str = "missing",
    start_menu_state: str = "missing",
    shortcut_target: Path | None = None,
    shortcut_icon: Path | None = None,
    shortcut_icon_state: str = "missing",
    shortcut_launcher: Path | None = None,
    legacy_auto_inject_state: str = "unknown",
    expected_launcher_version: str | None = None,
    global_command_version: str | None = None,
    shortcut_binary_version: str | None = None,
    stale_global_binaries: str = "unknown",
) -> InstallResult:
    install_external_launch_assets(paths, installation)
    return InstallResult(
        mode="external_launch",
        app_integration_state="fallback" if installation.kind != "missing" else "missing",
        restart_required=False,
        state_dir=paths.home,
        app_dir=installation.app_dir,
        codex_binary=installation.binary_path,
        fallback_reason=reason,
        message=message,
        shortcut_state=shortcut_state,
        start_menu_state=start_menu_state,
        shortcut_target=shortcut_target,
        shortcut_icon=shortcut_icon,
        shortcut_icon_state=shortcut_icon_state,
        shortcut_launcher=shortcut_launcher,
        legacy_auto_inject_state=legacy_auto_inject_state,
        expected_launcher_version=expected_launcher_version,
        global_command_version=global_command_version,
        shortcut_binary_version=shortcut_binary_version,
        stale_global_binaries=stale_global_binaries,
    )


def install_app(paths: RuntimePaths, repair: bool = False, from_postinstall: bool = False, shortcut_mode: str = "real") -> InstallResult:
    ensure_home(paths)
    if sys.platform == "win32":
        cleanup_legacy_windows_auto_inject()

    installation = detect_codex_installation()
    shortcut_result = InstallResult(
        mode="external_launch",
        app_integration_state="unknown",
        restart_required=False,
        state_dir=paths.home,
        shortcut_state="unsupported",
        start_menu_state="unsupported",
    )
    if sys.platform == "win32":
        shortcut_result = install_windows_shortcuts(paths, mode=shortcut_mode)

    if installation.kind == "missing":
        result = _fallback_result(
            paths,
            installation,
            "codex_app_not_found",
            "Codex App was not found. Install Codex Desktop first, then use `cxpp install-app` again.",
            shortcut_state=shortcut_result.shortcut_state,
            start_menu_state=shortcut_result.start_menu_state,
            shortcut_target=shortcut_result.shortcut_target,
            shortcut_icon=shortcut_result.shortcut_icon,
            shortcut_icon_state=shortcut_result.shortcut_icon_state,
            shortcut_launcher=shortcut_result.shortcut_launcher,
            legacy_auto_inject_state=shortcut_result.legacy_auto_inject_state,
            expected_launcher_version=shortcut_result.expected_launcher_version,
            global_command_version=shortcut_result.global_command_version,
            shortcut_binary_version=shortcut_result.shortcut_binary_version,
            stale_global_binaries=shortcut_result.stale_global_binaries,
        )
        record_install_state(paths, result)
        return result

    if installation.kind == "native" and installation.writable:
        try:
            install_native_patch(installation, paths)
        except (OSError, RuntimeError) as exc:
            result = _fallback_result(
                paths,
                installation,
                "native_patch_failed",
                f"Native Codex App patch failed: {exc}. Falling back to `cxpp launch`.",
                shortcut_state=shortcut_result.shortcut_state,
                start_menu_state=shortcut_result.start_menu_state,
                shortcut_target=shortcut_result.shortcut_target,
                shortcut_icon=shortcut_result.shortcut_icon,
                shortcut_icon_state=shortcut_result.shortcut_icon_state,
                shortcut_launcher=shortcut_result.shortcut_launcher,
                legacy_auto_inject_state=shortcut_result.legacy_auto_inject_state,
                expected_launcher_version=shortcut_result.expected_launcher_version,
                global_command_version=shortcut_result.global_command_version,
                shortcut_binary_version=shortcut_result.shortcut_binary_version,
                stale_global_binaries=shortcut_result.stale_global_binaries,
            )
            record_install_state(paths, result)
            return result

        result = InstallResult(
            mode="native_patch",
            app_integration_state="installed",
            restart_required=windows_codex_running(),
            state_dir=paths.home,
            app_dir=installation.app_dir,
            codex_binary=installation.binary_path,
            message=(
                "Codex++ assets were installed into the native Codex App resources. Legacy auto-inject remnants were removed."
                if not windows_codex_running()
                else "Codex++ assets were installed into the native Codex App resources. Legacy auto-inject remnants were removed. Fully exit Codex App and open it again to load the new integration."
            ),
            shortcut_state=shortcut_result.shortcut_state,
            start_menu_state=shortcut_result.start_menu_state,
            shortcut_target=shortcut_result.shortcut_target,
            shortcut_icon=shortcut_result.shortcut_icon,
            shortcut_icon_state=shortcut_result.shortcut_icon_state,
            shortcut_launcher=shortcut_result.shortcut_launcher,
            legacy_auto_inject_state=shortcut_result.legacy_auto_inject_state,
            expected_launcher_version=shortcut_result.expected_launcher_version,
            global_command_version=shortcut_result.global_command_version,
            shortcut_binary_version=shortcut_result.shortcut_binary_version,
            stale_global_binaries=shortcut_result.stale_global_binaries,
        )
        record_install_state(paths, result)
        return result

    if installation.kind == "msix":
        result = _fallback_result(
            paths,
            installation,
            "msix_installation",
            "Detected Microsoft Store / MSIX Codex App. Falling back to `cxpp launch` instead of modifying WindowsApps.",
            shortcut_state=shortcut_result.shortcut_state,
            start_menu_state=shortcut_result.start_menu_state,
            shortcut_target=shortcut_result.shortcut_target,
            shortcut_icon=shortcut_result.shortcut_icon,
            shortcut_icon_state=shortcut_result.shortcut_icon_state,
            shortcut_launcher=shortcut_result.shortcut_launcher,
            legacy_auto_inject_state=shortcut_result.legacy_auto_inject_state,
            expected_launcher_version=shortcut_result.expected_launcher_version,
            global_command_version=shortcut_result.global_command_version,
            shortcut_binary_version=shortcut_result.shortcut_binary_version,
            stale_global_binaries=shortcut_result.stale_global_binaries,
        )
        record_install_state(paths, result)
        return result

    result = _fallback_result(
        paths,
        installation,
        "app_dir_not_writable",
        "The Codex App install directory is not writable. Falling back to `cxpp launch`.",
        shortcut_state=shortcut_result.shortcut_state,
        start_menu_state=shortcut_result.start_menu_state,
        shortcut_target=shortcut_result.shortcut_target,
        shortcut_icon=shortcut_result.shortcut_icon,
        shortcut_icon_state=shortcut_result.shortcut_icon_state,
        shortcut_launcher=shortcut_result.shortcut_launcher,
        legacy_auto_inject_state=shortcut_result.legacy_auto_inject_state,
        expected_launcher_version=shortcut_result.expected_launcher_version,
        global_command_version=shortcut_result.global_command_version,
        shortcut_binary_version=shortcut_result.shortcut_binary_version,
        stale_global_binaries=shortcut_result.stale_global_binaries,
    )
    record_install_state(paths, result)
    return result


def start_codex_app(installation: CodexInstallation) -> bool:
    if installation.kind == "missing":
        return False

    if sys.platform == "win32":
        if installation.packaged_app_id:
            destination = f"shell:AppsFolder\\{installation.packaged_app_id}"
            try:
                result = subprocess.run(
                    ["explorer.exe", destination],
                    check=False,
                    cwd=str(Path.home()),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return result.returncode == 0
            except (OSError, subprocess.SubprocessError):
                return False
        if installation.binary_path is not None:
            try:
                subprocess.Popen(
                    [str(installation.binary_path)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    cwd=str(installation.binary_path.parent),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return True
            except (OSError, subprocess.SubprocessError):
                return False
        return False

    if installation.binary_path is not None:
        try:
            subprocess.Popen(
                [str(installation.binary_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                cwd=str(installation.binary_path.parent),
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False
    return False


def stop_codex_app() -> bool:
    if sys.platform != "win32":
        return False
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        "Write-Output 'stopped'"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            cwd=str(Path.home()),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def restart_codex_app(installation: CodexInstallation) -> bool:
    stopped = stop_codex_app()
    if not stopped:
        return False
    time.sleep(1)
    return start_codex_app(installation)
