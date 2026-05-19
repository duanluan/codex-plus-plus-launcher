# codex-plus-plus-launcher

`codex-plus-plus-launcher` 是 [Codex++](https://github.com/BigPizzaV3/CodexPlusPlus) 的安装和启动包装层。

它提供统一命令，帮助你把 Codex++ 安装到本机 Codex App，或在不适合直装时回退到显式启动模式。

如果你使用的是 Arch Linux，优先推荐直接安装 AUR 包：

- [codex-plus-plus](https://aur.archlinux.org/packages/codex-plus-plus)

## 安装

### 方法 1：npm

```bash
npm install -g @duanluan/codex-plus-plus-launcher
```

### 方法 2：一键脚本

Linux / macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/duanluan/codex-plus-plus-launcher/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/duanluan/codex-plus-plus-launcher/main/install.ps1 | iex
```

如果你明确想改用 `uv` 安装：

Linux / macOS:

```bash
bash install.sh --use-uv
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -UseUv
```

## 开始使用

`npm install -g` 会把 `cxpp`/`codexpp` 命令安装到 npm 全局目录。命令默认调用随 npm 包发布的本机二进制程序，不要求用户手动创建或进入 Python 虚拟环境。

安装时会把当前平台的二进制复制到 npm 全局 prefix 目录，避免 `node_modules` 包目录在升级时成为唯一入口。

安装过程会立即尝试把 Codex++ 集成到本机 Codex App。若检测到 Microsoft Store / MSIX 安装或原生目录不可写，则不会强改 `WindowsApps`，而是自动回退到 `cxpp launch` 的显式启动模式。

Windows/npm 路线默认把“更新 Codex++”收敛成“更新这个 wrapper 包”。也就是说，用户获取最新 Codex++ 能力的主要方式是升级 `@duanluan/codex-plus-plus-launcher`；wrapper 在发版时会重新同步并打包当时最新的上游 GitHub Release，而不是继续追 `main` 分支、也不要求用户单独在本机运行上游更新命令或安装 Python。

安装完成后不会强制重启 Codex Desktop；如果需要重启，命令会提示你手动重启或在交互终端里询问是否立即重启。

在 Windows 上，安装成功后还会创建：

- `cxpp` / `codexpp` 命令
- 桌面快捷方式 `Codex++`（后台启动，不显示黑色命令行窗口）
- 开始菜单入口 `Codex++`（后台启动，不显示黑色命令行窗口）

从旧版 `0.1.5` 升级到 `0.1.9+` 时，安装器会自动清理遗留的 auto-inject / watcher 注册项，避免旧接管逻辑继续导致原生 `Codex` 闪退。

如果需要手动安装或修复 App 集成：

```bash
cxpp install-app
```

检查安装状态：

```bash
cxpp doctor
```

`doctor` 中的关键字段语义：

- `package_version`：当前 npm wrapper 版本
- `bundled_upstream_version`：当前 wrapper 内置的上游 GitHub Release 版本
- `global_command_version`：当前 `cxpp` 全局命令实际命中的 wrapper 版本
- `stale_global_binaries`：当前 npm 全局 prefix 下是否还残留旧版 `cxpp-native-*`

启动 Codex++：

```bash
cxpp launch
```

## Windows 使用方式

在 Windows 上，npm 安装默认先尝试原生集成，再根据系统限制决定是否回退到 `cxpp launch`。

检查全局 npm 安装状态时，请使用：

```bash
npm list -g @duanluan/codex-plus-plus-launcher
```

如果命令输出 `install_mode=external_launch`，说明当前环境不适合直接写入 Codex App，这时请按下面的方式使用：

```bash
cxpp launch
```

## 常用命令

- `cxpp install-app`：尝试把 Codex++ 安装到本机 Codex App
- `cxpp repair-app`：重新探测并修复 App 集成
- `cxpp setup`：`install-app` 的兼容别名
- `cxpp repair`：`repair-app` 的兼容别名
- `cxpp doctor`：检查当前安装状态
- `cxpp launch`：手工启动 Codex++
- `cxpp help [command]`：查看帮助
- `cxpp version`：查看当前版本
- `codexpp ...`：与 `cxpp` 等价的保留命令

## 常见说明

本地状态、日志和回退运行资产默认放在 Windows 的 `%LOCALAPPDATA%\\CodexPlusPlusLauncher`。

## 本地开发验证

如果你在仓库里做本地 npm 测试，请先准备对应平台的 `bin/cxpp-<platform>-<arch>` 二进制，然后执行：

```bash
npm run build:binary-local
npm pack
npm run smoke:npm-local
```

`smoke:npm-local` 不会覆盖你真实桌面和开始菜单里的 `Codex++` 快捷方式；它只验证本地 npm 安装链路和命令可用性。

请使用 `npm` 或安装脚本，不再提供 PyPI 安装。
