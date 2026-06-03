# codex-plus-plus-launcher

`codex-plus-plus-launcher` 是 [Codex++](https://github.com/BigPizzaV3/CodexPlusPlus) 的 npm 包装层。npm 包内置上游 Codex++ Rust/Tauri sidecar，而不是把旧的 Python `codex_session_delete` 包当作主程序。

Windows 和 macOS 安装后会得到两个入口：

- `Codex++`：静默启动入口，负责启动 Codex 并注入增强功能。
- `Codex++ 管理工具`：上游 Tauri 控制面板，用于检查、修复、更新和管理增强功能。

Linux 支持需要先安装 [ilysenko/codex-desktop-linux](https://github.com/ilysenko/codex-desktop-linux)。npm 包会内置上游 Codex++ 静默 launcher，并为 `codex-desktop-linux` 生成一个 `codex.exe` shim，让 Codex++ 可以通过 `--app-path` 启动 Linux 版 Codex Desktop；Linux 暂不内置 Codex++ 管理工具。

## 安装

```bash
npm install -g @duanluan/codex-plus-plus-launcher
```

`npm install -g` 会安装 `cxpp`/`codexpp` 命令，并在支持的平台复制当前 npm 包内置的上游 sidecar：

- Windows：复制到 `%LOCALAPPDATA%\Programs\Codex++`，创建桌面和开始菜单的 `Codex++`、`Codex++ 管理工具` 快捷方式。
- macOS：优先创建 `/Applications/Codex++.app` 和 `/Applications/Codex++ 管理工具.app`，无权限时退到 `~/Applications`。
- Linux：如果已安装 `codex-desktop-linux`，复制 `codex-plus-plus` 静默 launcher，生成 `codex.exe` shim，并创建 `~/.local/share/applications/codex-plus-plus.desktop`。如果安装 npm 包时还没装 `codex-desktop-linux`，postinstall 会跳过集成且不报错；之后运行 `cxpp install-app` 或 `cxpp repair-app` 即可补装入口。

postinstall 只安装入口和快捷方式，不会自动启动 Codex++、管理工具或 Codex 进程。

Windows/npm 路线默认把“更新 Codex++”变成“更新这个 wrapper 包”。也就是说，用户获取最新 Codex++ 能力的主要方式是升级 `@duanluan/codex-plus-plus-launcher`；wrapper 在发版时会重新同步并打包当时最新的上游 GitHub Release，而不是要求用户单独运行上游 `.exe` / `.dmg` 安装器。

## 常用命令

- `cxpp launch` / `cxpp run`：启动内置上游静默入口。
- `cxpp manager`：打开内置上游管理工具。
- `cxpp install-app`：安装或修复 sidecar 和系统入口。
- `cxpp repair-app`：`install-app` 的别名。
- `cxpp doctor`：检查当前安装状态。
- `cxpp doctor --json`：输出机器可读的安装状态。
- `cxpp version`：查看 wrapper 版本。
- `codexpp ...`：与 `cxpp` 等价的保留命令。

`doctor --json` 中的关键字段：

- `package_version`：当前 npm wrapper 版本。
- `upstream_version`：当前 wrapper 内置的上游 GitHub Release 版本。
- `upstream_commit`：构建 sidecar 的上游 commit。
- `sidecar_dir`：npm 包内置 sidecar 目录。
- `install_root`：已复制 sidecar 和入口的本机目录。
- `silent_binary_state` / `manager_binary_state`：两个 sidecar 是否已安装。
- `silent_entrypoint_state` / `manager_entrypoint_state`：两个桌面入口是否已安装。
- Linux 还会显示 `linux_codex_desktop_state`、`linux_codex_desktop_start` 和 `linux_codex_shim_state`；`manager_binary_state` / `manager_entrypoint_state` 在 Linux 上为 `unsupported`。

## 本地开发验证

本地构建当前平台的上游 sidecar：

```bash
npm run build:sidecars-local
```

发布包验证要求 `upstream-bin/win32-x64`、`upstream-bin/darwin-x64`、`upstream-bin/darwin-arm64` 都包含上游二进制和图标，`upstream-bin/linux-x64` 包含上游静默 launcher，并包含 `upstream-release.json`：

```bash
npm run prepack
npm pack
npm run smoke:npm-local
```

`smoke:npm-local` 会设置 `CODEXPP_SHORTCUT_MODE=skip`，不会覆盖你真实桌面和开始菜单里的 `Codex++` 快捷方式。
