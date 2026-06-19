const messages = {
  zh: {
    missingPython: '缺少命令：python3、python 或 py',
    missingBinary: '缺少随 npm 包安装的 cxpp 二进制程序',
    missingSidecar: '缺少随 npm 包内置的 Codex++ 上游程序',
    missingLinuxCodexDesktop: '未找到 ilysenko/codex-desktop-linux 安装。请先安装 codex-desktop-linux，或设置 CODEXPP_LINUX_CODEX_START 指向 start.sh',
    missingPip: '当前 Python 缺少 pip，请先安装 pip',
    unsupportedPlatform: '当前 Codex++ 桌面版 npm 包暂不支持该平台',
    unsupportedLinuxManager: 'Linux 暂不提供 Codex++ 管理工具；请使用 cxpp launch 启动 Codex++',
    installingWrapper: '正在安装 codex-plus-plus-launcher',
    installingCodexPlusPlus: '正在安装 Codex++',
    installDone: '安装完成',
    lockedOldBinaryCloseAndRetry: '旧版 Codex++ 启动器仍在运行，无法替换全局启动器。请关闭 Codex++ / Codex App 后重新运行：npm i -g @duanluan/codex-plus-plus-launcher',
    lockedOldBinaryPrompt: '旧版 Codex++ 启动器仍在运行。是否关闭它并继续安装? [y/N] ',
    lockedOldBinaryPromptGui: '旧版 Codex++ 启动器仍在运行。是否关闭它并继续安装?',
    lockedOldBinaryPromptTitle: 'Codex++ 安装程序',
    runningCommandFailed: '命令执行失败',
    shortcutInstallFailed: '创建 Codex++ 快捷方式失败',
    retryingMirror: '直连失败，正在尝试 GitHub 镜像',
    retryingForceReinstall: '检测到损坏的 pip 安装记录，正在尝试跳过卸载直接覆盖安装',
    sidecarSelfHealOk: 'Codex++: 已自动更新本地 sidecar',
    sidecarSelfHealLocked: 'Codex++: 检测到本地 sidecar 与 npm 版本不一致，但当前正在运行；本次仍使用旧版启动。请退出 Codex 后重新执行 cxpp launch 完成升级。',
    sidecarSelfHealFailed: 'Codex++: sidecar 自愈失败，仍使用旧版启动',
  },
  en: {
    missingPython: 'missing command: python3, python, or py',
    missingBinary: 'missing bundled cxpp binary installed by the npm package',
    missingSidecar: 'missing bundled upstream Codex++ program installed by the npm package',
    missingLinuxCodexDesktop: 'could not find an ilysenko/codex-desktop-linux install; install codex-desktop-linux first or set CODEXPP_LINUX_CODEX_START to start.sh',
    missingPip: 'pip is not available for the selected Python runtime',
    unsupportedPlatform: 'the bundled Codex++ desktop npm package does not support this platform yet',
    unsupportedLinuxManager: 'Codex++ Manager is not bundled for Linux yet; use cxpp launch to start Codex++',
    installingWrapper: 'installing codex-plus-plus-launcher',
    installingCodexPlusPlus: 'installing Codex++',
    installDone: 'installation completed',
    lockedOldBinaryCloseAndRetry: 'An older Codex++ launcher is still running, so the global launcher cannot be replaced. Close Codex++ / Codex App and rerun: npm i -g @duanluan/codex-plus-plus-launcher',
    lockedOldBinaryPrompt: 'An older Codex++ launcher is still running. Close it and continue installation? [y/N] ',
    lockedOldBinaryPromptGui: 'An older Codex++ launcher is still running. Close it and continue installation?',
    lockedOldBinaryPromptTitle: 'Codex++ Installer',
    runningCommandFailed: 'command execution failed',
    shortcutInstallFailed: 'failed to create Codex++ shortcuts',
    retryingMirror: 'direct GitHub download failed, retrying with mirrors',
    retryingForceReinstall: 'detected a broken pip installation record, retrying without uninstall',
    sidecarSelfHealOk: 'Codex++: refreshed the local sidecar to match the npm package',
    sidecarSelfHealLocked: 'Codex++: the local sidecar is out of date but is currently running; using the old version for this launch. Quit Codex and re-run cxpp launch to finish the upgrade.',
    sidecarSelfHealFailed: 'Codex++: sidecar self-heal failed, falling back to the old version',
  },
};

function systemLocale() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().locale || '';
  } catch (_error) {
    return '';
  }
}

function language(env = process.env) {
  const raw = env.CODEXPP_LANG || env.LC_ALL || env.LC_MESSAGES || env.LANG || systemLocale();
  return raw.toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

function t(key, env = process.env) {
  const lang = language(env);
  return messages[lang][key] || messages.en[key] || key;
}

module.exports = { language, t };
