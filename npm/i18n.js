const messages = {
  zh: {
    missingPython: '缺少命令：python3、python 或 py',
    missingBinary: '缺少随 npm 包安装的 cxpp 二进制程序',
    missingPip: '当前 Python 缺少 pip，请先安装 pip',
    installingWrapper: '正在安装 codex-plus-plus-launcher',
    installingCodexPlusPlus: '正在安装 Codex++',
    installDone: '安装完成',
    lockedOldBinaryCloseAndRetry: '旧版 Codex++ 启动器仍在运行，无法替换全局启动器。请关闭 Codex++ / Codex App 后重新运行：npm i -g @duanluan/codex-plus-plus-launcher',
    lockedOldBinaryPrompt: '旧版 Codex++ 启动器仍在运行。是否关闭它并继续安装? [y/N] ',
    lockedOldBinaryPromptGui: '旧版 Codex++ 启动器仍在运行。是否关闭它并继续安装?',
    lockedOldBinaryPromptTitle: 'Codex++ 安装程序',
    runningCommandFailed: '命令执行失败',
    retryingMirror: '直连失败，正在尝试 GitHub 镜像',
    retryingForceReinstall: '检测到损坏的 pip 安装记录，正在尝试跳过卸载直接覆盖安装',
  },
  en: {
    missingPython: 'missing command: python3, python, or py',
    missingBinary: 'missing bundled cxpp binary installed by the npm package',
    missingPip: 'pip is not available for the selected Python runtime',
    installingWrapper: 'installing codex-plus-plus-launcher',
    installingCodexPlusPlus: 'installing Codex++',
    installDone: 'installation completed',
    lockedOldBinaryCloseAndRetry: 'An older Codex++ launcher is still running, so the global launcher cannot be replaced. Close Codex++ / Codex App and rerun: npm i -g @duanluan/codex-plus-plus-launcher',
    lockedOldBinaryPrompt: 'An older Codex++ launcher is still running. Close it and continue installation? [y/N] ',
    lockedOldBinaryPromptGui: 'An older Codex++ launcher is still running. Close it and continue installation?',
    lockedOldBinaryPromptTitle: 'Codex++ Installer',
    runningCommandFailed: 'command execution failed',
    retryingMirror: 'direct GitHub download failed, retrying with mirrors',
    retryingForceReinstall: 'detected a broken pip installation record, retrying without uninstall',
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
