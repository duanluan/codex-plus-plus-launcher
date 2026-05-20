# codex-plus-plus-launcher

`codex-plus-plus-launcher` is an npm wrapper for [Codex++](https://github.com/BigPizzaV3/CodexPlusPlus). The npm package bundles the upstream Rust/Tauri sidecars instead of treating the legacy Python `codex_session_delete` package as the main runtime.

Windows and macOS installs provide two entry points:

- `Codex++`: the silent launcher entry.
- `Codex++ Manager`: the upstream Tauri control panel for checks, repair, updates, and enhancement management.

Linux does not ship the upstream desktop sidecar in this npm package yet. Linux users should use the upstream project distribution path where available, such as the Arch Linux [codex-plus-plus](https://aur.archlinux.org/packages/codex-plus-plus) AUR package.

## Install

```bash
npm install -g @duanluan/codex-plus-plus-launcher
```

The npm install adds the `cxpp`/`codexpp` commands and copies the bundled upstream sidecars on supported platforms:

- Windows: copies to `%LOCALAPPDATA%\Programs\Codex++` and creates Desktop and Start Menu shortcuts for `Codex++` and `Codex++ Manager`.
- macOS: creates `/Applications/Codex++.app` and `/Applications/Codex++ 管理工具.app`, falling back to `~/Applications` if `/Applications` is not writable.
- Linux: commands can be installed, but upstream desktop sidecar mode is reported as unsupported.

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

## Local Verification

Build the upstream sidecars for the current platform:

```bash
npm run build:sidecars-local
```

Package verification expects `upstream-bin/win32-x64`, `upstream-bin/darwin-x64`, and `upstream-bin/darwin-arm64` to contain the upstream binaries, icons, and `upstream-release.json`:

```bash
npm run prepack
npm pack
npm run smoke:npm-local
```

`smoke:npm-local` sets `CODEXPP_SHORTCUT_MODE=skip`, so it does not overwrite your real Desktop or Start Menu shortcuts.
