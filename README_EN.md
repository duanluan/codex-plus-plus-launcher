# codex-plus-plus-launcher

Install via npm or the install scripts. The npm package installs the `cxpp`/`codexpp` commands into npm's global bin directory. Those commands default to the bundled native `cxpp` binary shipped in the npm package.

During install, the current platform binary is copied into npm's global prefix so the npm package directory under `node_modules` is not the only runnable entry point during future upgrades.

The npm install step immediately attempts to integrate Codex++ with the local Codex App. If the machine uses the Microsoft Store / MSIX build or the native install directory is not writable, the installer does not try to patch `WindowsApps`; it falls back to explicit `cxpp launch` mode instead.

On Windows/npm, “updating Codex++” is intentionally collapsed into “updating this wrapper package”. Users are not expected to install Python or run a separate upstream updater locally; each wrapper release rebuilds and republishes the latest upstream GitHub Release instead of tracking the `main` branch directly.

The installer does not force-restart Codex Desktop. If a restart is required, it will either ask in an interactive terminal or print a manual restart instruction.

Check global npm installation status with `npm list -g @duanluan/codex-plus-plus-launcher`.

Important `doctor` fields:

- `package_version`: the npm wrapper version
- `bundled_upstream_version`: the upstream GitHub Release version bundled inside this wrapper
- `global_command_version`: the wrapper version actually resolved by the global `cxpp` command
- `stale_global_binaries`: whether old `cxpp-native-*` binaries still remain in the current npm global prefix

On Windows, a successful install also creates:

- `cxpp` / `codexpp` commands
- a desktop shortcut named `Codex++` that launches in the background without a console window
- a Start Menu entry named `Codex++` that launches in the background without a console window

Upgrading from `0.1.5` to `0.1.9+` automatically removes legacy auto-inject / watcher remnants so the old takeover path cannot keep crashing the native `Codex` app.

For local npm verification in this repo, provide the matching `bin/cxpp-<platform>-<arch>` binary first, then run:

```bash
npm run build:binary-local
npm pack
npm run smoke:npm-local
```

`smoke:npm-local` does not overwrite your real desktop or Start Menu `Codex++` shortcuts. It only validates the local npm installation flow and command usability.
