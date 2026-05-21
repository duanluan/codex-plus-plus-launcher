# codex-plus-plus-launcher

`codex-plus-plus-launcher` is an npm wrapper for [Codex++](https://github.com/BigPizzaV3/CodexPlusPlus). The npm package bundles the upstream Rust/Tauri sidecars instead of treating the legacy Python `codex_session_delete` package as the main runtime.

Windows and macOS installs provide two entry points:

- `Codex++`: the silent launcher entry.
- `Codex++ Manager`: the upstream Tauri control panel for checks, repair, updates, and enhancement management.

Linux support requires [ilysenko/codex-desktop-linux](https://github.com/ilysenko/codex-desktop-linux) to be installed first. The npm package bundles the upstream Codex++ silent launcher and generates a `codex.exe` shim for `codex-desktop-linux`, so Codex++ can launch the Linux Codex Desktop through `--app-path`; Codex++ Manager is not bundled on Linux yet.

## Install

```bash
npm install -g @duanluan/codex-plus-plus-launcher
```

The npm install adds the `cxpp`/`codexpp` commands and copies the bundled upstream sidecars on supported platforms:

- Windows: copies to `%LOCALAPPDATA%\Programs\Codex++` and creates Desktop and Start Menu shortcuts for `Codex++` and `Codex++ Manager`.
- macOS: creates `/Applications/Codex++.app` and `/Applications/Codex++ 管理工具.app`, falling back to `~/Applications` if `/Applications` is not writable.
- Linux: if `codex-desktop-linux` is installed, copies the `codex-plus-plus` silent launcher, generates a `codex.exe` shim, and creates `~/.local/share/applications/codex-plus-plus.desktop`. If `codex-desktop-linux` is missing during npm install, postinstall skips integration without failing; run `cxpp install-app` or `cxpp repair-app` after installing it.

The postinstall step only installs entry points and shortcuts. It does not auto-launch Codex++, the manager UI, or any Codex process.

On npm, “updating Codex++” is intentionally collapsed into “updating this wrapper package”. Each wrapper release rebuilds and republishes the latest upstream GitHub Release; users are not expected to run upstream `.exe` / `.dmg` installers separately.

## Commands

- `cxpp launch` / `cxpp run`: launch the bundled upstream silent entry.
- `cxpp manager`: open the bundled upstream manager.
- `cxpp install-app`: install or repair sidecars and system entry points.
- `cxpp repair-app`: alias of `install-app`.
- `cxpp doctor`: inspect local state.
- `cxpp doctor --json`: print machine-readable state.
- `cxpp version`: print the wrapper version.
- `codexpp ...`: reserved alias for `cxpp`.

Important `doctor --json` fields:

- `package_version`: the npm wrapper version.
- `upstream_version`: the upstream GitHub Release version bundled inside this wrapper.
- `upstream_commit`: the upstream commit used to build the sidecars.
- `sidecar_dir`: the bundled sidecar directory inside the npm package.
- `install_root`: the local sidecar and entrypoint install directory.
- `silent_binary_state` / `manager_binary_state`: whether each sidecar is installed.
- `silent_entrypoint_state` / `manager_entrypoint_state`: whether each desktop entry point is installed.
- Linux also reports `linux_codex_desktop_state`, `linux_codex_desktop_start`, and `linux_codex_shim_state`; `manager_binary_state` / `manager_entrypoint_state` are `unsupported` on Linux.

## Local Verification

Build the upstream sidecars for the current platform:

```bash
npm run build:sidecars-local
```

Package verification expects `upstream-bin/win32-x64`, `upstream-bin/darwin-x64`, and `upstream-bin/darwin-arm64` to contain the upstream binaries and icons, `upstream-bin/linux-x64` to contain the upstream silent launcher, and `upstream-release.json` to be present:

```bash
npm run prepack
npm pack
npm run smoke:npm-local
```

`smoke:npm-local` sets `CODEXPP_SHORTCUT_MODE=skip`, so it does not overwrite your real Desktop or Start Menu shortcuts.
