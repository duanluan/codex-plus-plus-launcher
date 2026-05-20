const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const { spawn, spawnSync } = require('node:child_process');
const { t } = require('./i18n.js');

const SUPPORTED_PLATFORMS = new Set(['win32-x64', 'darwin-x64', 'darwin-arm64']);
const SILENT_BINARY = 'codex-plus-plus';
const MANAGER_BINARY = 'codex-plus-plus-manager';
const SILENT_NAME = 'Codex++';
const MANAGER_NAME = 'Codex++ 管理工具';

function optionValue(options, key, fallback) {
  const value = options[key];
  if (typeof value === 'function') {
    return value(options);
  }
  if (value !== undefined && value !== null) {
    return value;
  }
  return typeof fallback === 'function' ? fallback() : fallback;
}

function packageRoot() {
  return path.resolve(__dirname, '..');
}

function packageVersion(options = {}) {
  const root = optionValue(options, 'packageRoot', packageRoot);
  return require(path.join(root, 'package.json')).version;
}

function platformKey(platform = process.platform, arch = process.arch) {
  return `${platform}-${arch}`;
}

function executableName(name, platform = process.platform) {
  return platform === 'win32' ? `${name}.exe` : name;
}

function upstreamBinDir(options = {}) {
  const root = optionValue(options, 'packageRoot', packageRoot);
  const platform = optionValue(options, 'platform', process.platform);
  const arch = optionValue(options, 'arch', process.arch);
  return path.join(root, 'upstream-bin', platformKey(platform, arch));
}

function upstreamMetadataPath(options = {}) {
  const root = optionValue(options, 'packageRoot', packageRoot);
  return path.join(root, 'upstream-bin', 'upstream-release.json');
}

function readJsonFile(candidate, fsImpl = fs) {
  try {
    return JSON.parse(fsImpl.readFileSync(candidate, 'utf8'));
  } catch (_error) {
    return null;
  }
}

function upstreamMetadata(options = {}) {
  return readJsonFile(upstreamMetadataPath(options), options.fs || fs) || {};
}

function bundledUpstreamVersion(options = {}) {
  const metadata = upstreamMetadata(options);
  return metadata.version || metadata.tag || metadata.upstream_version || null;
}

function bundledSidecarPath(kind, options = {}) {
  const fsImpl = options.fs || fs;
  const platform = optionValue(options, 'platform', process.platform);
  const binary = kind === 'manager' ? MANAGER_BINARY : SILENT_BINARY;
  const candidate = path.join(upstreamBinDir(options), executableName(binary, platform));
  if (fsImpl.existsSync(candidate)) {
    return candidate;
  }
  return candidate;
}

function bundledIconPath(options = {}) {
  const root = optionValue(options, 'packageRoot', packageRoot);
  const platformDir = upstreamBinDir(options);
  for (const candidate of [
    path.join(platformDir, 'codex-plus-plus.ico'),
    path.join(platformDir, 'codex-plus-plus.png'),
    path.join(root, 'codex_plus_plus_launcher', 'assets', 'codex-plus-plus.ico'),
  ]) {
    if ((options.fs || fs).existsSync(candidate)) {
      return candidate;
    }
  }
  return path.join(root, 'codex_plus_plus_launcher', 'assets', 'codex-plus-plus.ico');
}

function assertSupportedPlatform(options = {}) {
  const key = platformKey(optionValue(options, 'platform', process.platform), optionValue(options, 'arch', process.arch));
  if (!SUPPORTED_PLATFORMS.has(key)) {
    const error = new Error(`${t('unsupportedPlatform', options.env || process.env)}: ${key}`);
    error.code = 'CODEXPP_UNSUPPORTED_PLATFORM';
    throw error;
  }
  return key;
}

function assertBundledSidecars(options = {}) {
  const fsImpl = options.fs || fs;
  assertSupportedPlatform(options);
  const missing = [bundledSidecarPath('silent', options), bundledSidecarPath('manager', options)].filter((candidate) => !fsImpl.existsSync(candidate));
  if (missing.length > 0) {
    const error = new Error(`${t('missingSidecar', options.env || process.env)}: ${missing.join(', ')}`);
    error.code = 'CODEXPP_MISSING_SIDECAR';
    throw error;
  }
}

function defaultInstallRoot(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const env = options.env || process.env;
  const homeDir = optionValue(options, 'homeDir', () => os.homedir());
  if (env.CODEXPP_INSTALL_ROOT) {
    return env.CODEXPP_INSTALL_ROOT;
  }
  if (platform === 'win32') {
    const local = env.LOCALAPPDATA || path.join(homeDir, 'AppData', 'Local');
    return path.join(local, 'Programs', 'Codex++');
  }
  if (platform === 'darwin') {
    return '/Applications';
  }
  return path.join(homeDir, '.local', 'share', 'Codex++');
}

function fallbackMacInstallRoot(options = {}) {
  return optionValue(options, 'fallbackInstallRoot', () => path.join(optionValue(options, 'homeDir', () => os.homedir()), 'Applications'));
}

function installedSidecarPath(kind, options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const root = optionValue(options, 'installRoot', () => detectedInstallRoot(options));
  const binary = kind === 'manager' ? MANAGER_BINARY : SILENT_BINARY;
  return path.join(root, executableName(binary, platform));
}

function detectedInstallRoot(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const requested = optionValue(options, 'requestedInstallRoot', () => defaultInstallRoot(options));
  if (platform !== 'darwin') {
    return requested;
  }
  const fsImpl = options.fs || fs;
  const hasRequestedSidecar = fsImpl.existsSync(path.join(requested, SILENT_BINARY)) || fsImpl.existsSync(path.join(requested, MANAGER_BINARY));
  if (hasRequestedSidecar) {
    return requested;
  }
  const fallback = fallbackMacInstallRoot(options);
  const hasFallbackSidecar = fsImpl.existsSync(path.join(fallback, SILENT_BINARY)) || fsImpl.existsSync(path.join(fallback, MANAGER_BINARY));
  if (hasFallbackSidecar) {
    return fallback;
  }
  return requested;
}

function isPermissionError(error) {
  return error && (error.code === 'EPERM' || error.code === 'EACCES');
}

function sleepSync(milliseconds) {
  if (milliseconds <= 0) {
    return;
  }
  const buffer = new SharedArrayBuffer(4);
  const view = new Int32Array(buffer);
  Atomics.wait(view, 0, 0, milliseconds);
}

function rmSyncWithRetries(fsImpl, candidate, options = {}) {
  const attempts = optionValue(options, 'removeRetryAttempts', 10);
  const delay = optionValue(options, 'removeRetryDelayMs', 200);
  let lastError = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      fsImpl.rmSync(candidate, { force: true, recursive: true });
      return;
    } catch (error) {
      if (!isPermissionError(error) || attempt === attempts) {
        throw error;
      }
      lastError = error;
      sleepSync(delay);
    }
  }

  if (lastError) {
    throw lastError;
  }
}

function parsePowerShellJson(stdout) {
  const raw = String(stdout || '').trim();
  if (!raw) {
    return [];
  }
  const payload = JSON.parse(raw);
  return Array.isArray(payload) ? payload : [payload];
}

function findRunningProcessesForPath(binaryPath, options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  if (platform !== 'win32') {
    return [];
  }

  const run = options.spawnSync || spawnSync;
  const env = { ...(options.env || process.env), CODEXPP_LOCKED_BINARY: binaryPath };
  const script = [
    '$ErrorActionPreference = "SilentlyContinue"',
    '$target = [System.IO.Path]::GetFullPath($env:CODEXPP_LOCKED_BINARY)',
    'Get-CimInstance Win32_Process | Where-Object {',
    '  $_.ExecutablePath -and ([System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $target)',
    '} | Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress',
  ].join('\n');
  const result = run('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script], {
    encoding: 'utf8',
    env,
    windowsHide: true,
  });
  if (result.status !== 0) {
    return [];
  }
  try {
    return parsePowerShellJson(result.stdout);
  } catch (_error) {
    return [];
  }
}

function terminateProcesses(processes, options = {}) {
  const ids = [...new Set(processes.map((processInfo) => Number(processInfo.ProcessId)).filter((id) => Number.isInteger(id) && id > 0))];
  if (ids.length === 0) {
    return;
  }

  const run = options.spawnSync || spawnSync;
  const env = { ...(options.env || process.env), CODEXPP_PROCESS_IDS: ids.join(',') };
  const script = [
    '$ErrorActionPreference = "SilentlyContinue"',
    '$ids = $env:CODEXPP_PROCESS_IDS -split "," | Where-Object { $_ } | ForEach-Object { [int]$_ }',
    'foreach ($id in $ids) {',
    '  $process = Get-Process -Id $id -ErrorAction SilentlyContinue',
    '  if ($process) {',
    '    Stop-Process -InputObject $process -Force -ErrorAction SilentlyContinue',
    '    Wait-Process -Id $id -Timeout 5 -ErrorAction SilentlyContinue',
    '  }',
    '}',
  ].join('\n');
  run('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script], {
    encoding: 'utf8',
    env,
    stdio: 'ignore',
    windowsHide: true,
  });
}

function isTruthyEnv(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
}

function isKnownNonInteractiveEnv(env = process.env) {
  return ['CI', 'TF_BUILD', 'GITHUB_ACTIONS', 'BUILD_BUILDID', 'JENKINS_URL', 'TEAMCITY_VERSION'].some((key) => {
    const value = env[key];
    return value !== undefined && value !== null && !['', '0', 'false', 'no', 'off'].includes(String(value).trim().toLowerCase());
  });
}

function isTerminalInteractive(options = {}) {
  const input = options.stdin || process.stdin;
  const output = options.stdout || process.stdout;
  return Boolean(input && input.isTTY && output && output.isTTY);
}

function isWindowsGuiPromptAvailable(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const env = options.env || process.env;
  if (platform !== 'win32') {
    return false;
  }
  if (isTruthyEnv(env.CODEXPP_FORCE_NONINTERACTIVE) || isTruthyEnv(env.CODEXPP_DISABLE_WINDOWS_PROMPT)) {
    return false;
  }
  if (isTruthyEnv(env.CODEXPP_ENABLE_WINDOWS_PROMPT)) {
    return true;
  }
  return !isKnownNonInteractiveEnv(env);
}

function promptYesNo(question, options = {}) {
  const input = options.stdin || process.stdin;
  const output = options.stdout || process.stdout;
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input, output });
    rl.question(question, (answer) => {
      rl.close();
      resolve(['y', 'yes'].includes(String(answer || '').trim().toLowerCase()));
    });
  });
}

function promptYesNoWindowsPopup(question, options = {}) {
  const run = options.spawnSync || spawnSync;
  const env = {
    ...(options.env || process.env),
    CODEXPP_LOCKED_BINARY_PROMPT: question,
    CODEXPP_LOCKED_BINARY_PROMPT_TITLE: t('lockedOldBinaryPromptTitle', options.env || process.env),
    CODEXPP_PROMPT_TIMEOUT_SECONDS: String(optionValue(options, 'promptTimeoutSeconds', 60)),
  };
  const script = [
    '$ErrorActionPreference = "Stop"',
    '$shell = New-Object -ComObject WScript.Shell',
    '$timeout = [int]$env:CODEXPP_PROMPT_TIMEOUT_SECONDS',
    '$result = $shell.Popup($env:CODEXPP_LOCKED_BINARY_PROMPT, $timeout, $env:CODEXPP_LOCKED_BINARY_PROMPT_TITLE, 308)',
    'if ($result -eq 6) { exit 0 }',
    'exit 1',
  ].join('\n');
  const result = run('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script], {
    encoding: 'utf8',
    env,
    stdio: 'ignore',
    windowsHide: true,
  });
  return result.status === 0;
}

async function confirmCloseLockedBinary(candidate, options = {}) {
  const env = options.env || process.env;
  if (isTerminalInteractive(options)) {
    const ask = options.promptYesNo || promptYesNo;
    return ask(t('lockedOldBinaryPrompt', env), options);
  }
  if (isWindowsGuiPromptAvailable(options)) {
    const ask = options.promptYesNoWindowsPopup || promptYesNoWindowsPopup;
    return ask(`${t('lockedOldBinaryPromptGui', env)}\n\n${candidate}`, options);
  }
  return false;
}

function lockedBinaryError(binaryPath, processes, cause, options = {}) {
  const env = options.env || process.env;
  const details = [`locked_binary=${binaryPath}`];
  const ids = processes.map((processInfo) => processInfo.ProcessId).filter(Boolean);
  if (ids.length > 0) {
    details.push(`process_ids=${ids.join(',')}`);
  }
  const error = new Error(`${t('lockedOldBinaryCloseAndRetry', env)}\n${details.join('\n')}`);
  error.code = 'CODEXPP_LOCKED_OLD_BINARY';
  error.cause = cause;
  return error;
}

async function removePath(candidate, options = {}) {
  const fsImpl = options.fs || fs;
  const platform = optionValue(options, 'platform', process.platform);
  try {
    fsImpl.rmSync(candidate, { force: true, recursive: true });
    return;
  } catch (error) {
    if (platform !== 'win32' || !isPermissionError(error)) {
      throw error;
    }

    const findProcesses = options.findRunningProcessesForPath || findRunningProcessesForPath;
    const processes = findProcesses(candidate, options);
    if (processes.length === 0) {
      throw lockedBinaryError(candidate, processes, error, options);
    }

    const shouldClose = await confirmCloseLockedBinary(candidate, options);
    if (!shouldClose) {
      throw lockedBinaryError(candidate, processes, error, options);
    }

    const terminate = options.terminateProcesses || terminateProcesses;
    terminate(processes, options);
    try {
      rmSyncWithRetries(fsImpl, candidate, options);
    } catch (retryError) {
      throw lockedBinaryError(candidate, processes, retryError, options);
    }
  }
}

function filesMatch(fsImpl, source, target) {
  try {
    const sourceStats = fsImpl.statSync(source);
    const targetStats = fsImpl.statSync(target);
    if (sourceStats.size !== targetStats.size) {
      return false;
    }
    return fsImpl.readFileSync(source).equals(fsImpl.readFileSync(target));
  } catch (_error) {
    return false;
  }
}

async function copyReplacingChangedFile(source, target, options = {}) {
  const fsImpl = options.fs || fs;
  if (fsImpl.existsSync(target) && filesMatch(fsImpl, source, target)) {
    fsImpl.chmodSync(target, 0o755);
    return false;
  }
  if (fsImpl.existsSync(target)) {
    await removePath(target, options);
  }
  fsImpl.mkdirSync(path.dirname(target), { recursive: true });
  fsImpl.copyFileSync(source, target);
  fsImpl.chmodSync(target, 0o755);
  return true;
}

async function installSidecars(options = {}) {
  const fsImpl = options.fs || fs;
  assertBundledSidecars(options);
  const installRoot = installSidecarRoot(options);
  fsImpl.mkdirSync(installRoot, { recursive: true });
  const installed = {};
  for (const kind of ['silent', 'manager']) {
    const source = bundledSidecarPath(kind, options);
    const target = installedSidecarPath(kind, { ...options, installRoot });
    await copyReplacingChangedFile(source, target, { ...options, target });
    installed[kind] = target;
  }
  const icon = bundledIconPath(options);
  if (fsImpl.existsSync(icon)) {
    const iconTarget = path.join(installRoot, path.basename(icon));
    fsImpl.copyFileSync(icon, iconTarget);
    installed.icon = iconTarget;
  }
  installed.installRoot = installRoot;
  return installed;
}

function installSidecarRoot(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const fsImpl = options.fs || fs;
  const requested = optionValue(options, 'installRoot', () => defaultInstallRoot(options));
  if (platform !== 'darwin') {
    return requested;
  }
  try {
    fsImpl.mkdirSync(requested, { recursive: true });
    fsImpl.accessSync(requested, fs.constants.W_OK);
    return requested;
  } catch (_error) {
    const fallback = fallbackMacInstallRoot(options);
    fsImpl.mkdirSync(fallback, { recursive: true });
    return fallback;
  }
}

function windowsShortcutScript(specs) {
  const lines = [
    '$ErrorActionPreference = "Stop"',
    '$Shell = New-Object -ComObject WScript.Shell',
  ];
  for (const spec of specs) {
    lines.push(`$Shortcut = $Shell.CreateShortcut(${psQuote(spec.path)})`);
    lines.push(`$Shortcut.TargetPath = ${psQuote(spec.target)}`);
    lines.push(`$Shortcut.Arguments = ${psQuote(spec.arguments || '')}`);
    lines.push(`$Shortcut.WorkingDirectory = ${psQuote(spec.workingDirectory || path.dirname(spec.target))}`);
    lines.push(`$Shortcut.Description = ${psQuote(spec.description)}`);
    if (spec.icon) {
      lines.push(`$Shortcut.IconLocation = ${psQuote(spec.icon)}`);
    }
    lines.push('$Shortcut.Save()');
  }
  return lines.join('\n');
}

function psQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function windowsEntrypointPaths(options = {}) {
  const env = options.env || process.env;
  const desktop = optionValue(options, 'desktopDir', () => path.join(os.homedir(), 'Desktop'));
  const appData = env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
  const startMenu = optionValue(options, 'startMenuDir', () => path.join(appData, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Codex++'));
  return {
    desktopSilent: path.join(desktop, `${SILENT_NAME}.lnk`),
    desktopManager: path.join(desktop, `${MANAGER_NAME}.lnk`),
    startMenuSilent: path.join(startMenu, `${SILENT_NAME}.lnk`),
    startMenuManager: path.join(startMenu, `${MANAGER_NAME}.lnk`),
    startMenu,
  };
}

function installWindowsEntrypoints(installed, options = {}) {
  const fsImpl = options.fs || fs;
  const run = options.spawnSync || spawnSync;
  const paths = windowsEntrypointPaths(options);
  fsImpl.mkdirSync(path.dirname(paths.desktopSilent), { recursive: true });
  fsImpl.mkdirSync(paths.startMenu, { recursive: true });
  const specs = [
    [paths.desktopSilent, installed.silent, 'Launch Codex++ silently'],
    [paths.desktopManager, installed.manager, 'Open Codex++ management tool'],
    [paths.startMenuSilent, installed.silent, 'Launch Codex++ silently'],
    [paths.startMenuManager, installed.manager, 'Open Codex++ management tool'],
  ].map(([shortcutPath, target, description]) => ({
    path: shortcutPath,
    target,
    description,
    icon: target,
  }));
  const result = run('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', windowsShortcutScript(specs)], {
    encoding: 'utf8',
    windowsHide: true,
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || t('shortcutInstallFailed', options.env || process.env));
  }
  return paths;
}

function macAppRoot(options = {}) {
  const fsImpl = options.fs || fs;
  const requested = optionValue(options, 'installRoot', () => defaultInstallRoot(options));
  try {
    fsImpl.mkdirSync(requested, { recursive: true });
    fsImpl.accessSync(requested, fs.constants.W_OK);
    return requested;
  } catch (_error) {
    const fallback = fallbackMacInstallRoot(options);
    fsImpl.mkdirSync(fallback, { recursive: true });
    return fallback;
  }
}

function macInfoPlist(displayName, executableName, version, lsuiElement) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>${displayName}</string>
  <key>CFBundleDisplayName</key>
  <string>${displayName}</string>
  <key>CFBundleIdentifier</key>
  <string>com.bigpizzav3.codexplusplus${displayName === MANAGER_NAME ? '.manager' : ''}</string>
  <key>CFBundleVersion</key>
  <string>${version}</string>
  <key>CFBundleShortVersionString</key>
  <string>${version}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>${executableName}</string>
  <key>CFBundleIconFile</key>
  <string>codex-plus-plus.png</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>LSUIElement</key>
  <${lsuiElement ? 'true' : 'false'}/>
</dict>
</plist>
`;
}

async function writeMacAppBundle(appRoot, appName, executableName, binaryPath, options = {}) {
  const fsImpl = options.fs || fs;
  const app = path.join(appRoot, `${appName}.app`);
  const contents = path.join(app, 'Contents');
  const macos = path.join(contents, 'MacOS');
  const resources = path.join(contents, 'Resources');
  if (fsImpl.existsSync(app)) {
    await removePath(app, options);
  }
  fsImpl.mkdirSync(macos, { recursive: true });
  fsImpl.mkdirSync(resources, { recursive: true });
  fsImpl.writeFileSync(path.join(contents, 'Info.plist'), macInfoPlist(appName, executableName, bundledUpstreamVersion(options) || packageVersion(options), appName === SILENT_NAME), 'utf8');
  fsImpl.copyFileSync(binaryPath, path.join(macos, executableName));
  fsImpl.chmodSync(path.join(macos, executableName), 0o755);
  const icon = bundledIconPath({ ...options, platform: 'darwin' });
  if (fsImpl.existsSync(icon)) {
    fsImpl.copyFileSync(icon, path.join(resources, path.basename(icon).endsWith('.png') ? 'codex-plus-plus.png' : path.basename(icon)));
  }
  return app;
}

async function installMacEntrypoints(installed, options = {}) {
  const appRoot = macAppRoot(options);
  const silent = await writeMacAppBundle(appRoot, SILENT_NAME, 'CodexPlusPlus', installed.silent, options);
  const manager = await writeMacAppBundle(appRoot, MANAGER_NAME, 'CodexPlusPlusManager', installed.manager, options);
  return { appRoot, silent, manager };
}

async function installEntrypoints(installed, options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  if (String((options.env || process.env).CODEXPP_SHORTCUT_MODE).toLowerCase() === 'skip') {
    return { skipped: true };
  }
  if (platform === 'win32') {
    return installWindowsEntrypoints(installed, options);
  }
  if (platform === 'darwin') {
    return installMacEntrypoints(installed, options);
  }
  return { unsupported: true };
}

async function installApp(options = {}) {
  const installed = await installSidecars(options);
  const entrypoints = await installEntrypoints(installed, { ...options, installRoot: installed.installRoot });
  return { installed, entrypoints };
}

function inspectEntrypoints(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const fsImpl = options.fs || fs;
  if (platform === 'win32') {
    const paths = windowsEntrypointPaths(options);
    return {
      silent: fsImpl.existsSync(paths.desktopSilent) || fsImpl.existsSync(paths.startMenuSilent) ? 'installed' : 'missing',
      manager: fsImpl.existsSync(paths.desktopManager) || fsImpl.existsSync(paths.startMenuManager) ? 'installed' : 'missing',
      silent_path: paths.desktopSilent,
      manager_path: paths.desktopManager,
    };
  }
  if (platform === 'darwin') {
    const primary = optionValue(options, 'installRoot', () => defaultInstallRoot(options));
    const fallback = fallbackMacInstallRoot(options);
    const silentPrimary = path.join(primary, `${SILENT_NAME}.app`);
    const managerPrimary = path.join(primary, `${MANAGER_NAME}.app`);
    const silentFallback = path.join(fallback, `${SILENT_NAME}.app`);
    const managerFallback = path.join(fallback, `${MANAGER_NAME}.app`);
    return {
      silent: fsImpl.existsSync(silentPrimary) || fsImpl.existsSync(silentFallback) ? 'installed' : 'missing',
      manager: fsImpl.existsSync(managerPrimary) || fsImpl.existsSync(managerFallback) ? 'installed' : 'missing',
      silent_path: fsImpl.existsSync(silentPrimary) ? silentPrimary : silentFallback,
      manager_path: fsImpl.existsSync(managerPrimary) ? managerPrimary : managerFallback,
    };
  }
  return { silent: 'unsupported', manager: 'unsupported' };
}

function installedSidecars(options = {}) {
  const fsImpl = options.fs || fs;
  const silent = installedSidecarPath('silent', options);
  const manager = installedSidecarPath('manager', options);
  return {
    silent,
    manager,
    silent_state: fsImpl.existsSync(silent) ? 'installed' : 'missing',
    manager_state: fsImpl.existsSync(manager) ? 'installed' : 'missing',
  };
}

function doctorReport(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const arch = optionValue(options, 'arch', process.arch);
  const installRoot = optionValue(options, 'installRoot', () => detectedInstallRoot(options));
  const sidecars = installedSidecars(options);
  const entrypoints = inspectEntrypoints(options);
  const supported = SUPPORTED_PLATFORMS.has(platformKey(platform, arch));
  return {
    platform,
    arch,
    supported: supported ? 'yes' : 'no',
    package_version: packageVersion(options),
    upstream_version: bundledUpstreamVersion(options) || 'missing',
    upstream_commit: upstreamMetadata(options).commit || 'missing',
    sidecar_dir: upstreamBinDir(options),
    install_root: installRoot,
    silent_binary: sidecars.silent,
    silent_binary_state: sidecars.silent_state,
    manager_binary: sidecars.manager,
    manager_binary_state: sidecars.manager_state,
    silent_entrypoint_state: entrypoints.silent,
    manager_entrypoint_state: entrypoints.manager,
    silent_entrypoint: entrypoints.silent_path || '',
    manager_entrypoint: entrypoints.manager_path || '',
  };
}

function printDoctor(jsonMode, options = {}) {
  const report = doctorReport(options);
  if (jsonMode) {
    console.log(JSON.stringify(report, null, 2));
    return 0;
  }
  for (const [key, value] of Object.entries(report)) {
    console.log(`${key}=${value}`);
  }
  return 0;
}

function spawnSidecar(kind, args = [], options = {}) {
  assertSupportedPlatform(options);
  const platform = optionValue(options, 'platform', process.platform);
  const cwd = options.cwd || os.homedir();
  const installed = installedSidecarPath(kind, options);
  const bundled = bundledSidecarPath(kind, options);
  const binary = (options.fs || fs).existsSync(installed) ? installed : bundled;
  if (!(options.fs || fs).existsSync(binary)) {
    return { status: 1, error: new Error(`${t('missingSidecar', options.env || process.env)}: ${binary}`) };
  }
  const env = options.env || process.env;
  if (platform === 'win32' && !options.forceSync && !options.spawnSync) {
    const spawnAsync = options.spawn || spawn;
    const command = options.spawn ? binary : 'cmd.exe';
    const commandArgs = options.spawn ? args : ['/d', '/s', '/c', 'start', '""', binary, ...args];
    let child;
    try {
      child = spawnAsync(command, commandArgs, {
        stdio: 'ignore',
        cwd,
        env,
        detached: true,
        windowsHide: true,
      });
    } catch (error) {
      if (options.spawnSync) {
        return options.spawnSync(binary, args, {
          stdio: 'inherit',
          cwd,
          env,
          windowsHide: true,
        });
      }
      return { status: 1, error };
    }
    if (child && typeof child.once === 'function') {
      child.once('error', () => {});
    }
    if (child && typeof child.unref === 'function') {
      child.unref();
    }
    return { status: 0, pid: child && child.pid };
  }
  const run = options.spawnSync || spawnSync;
  return run(binary, args, {
    stdio: 'inherit',
    cwd,
    env,
    windowsHide: platform === 'win32',
  });
}

function printHelp() {
  console.log(`Codex++ launcher wrapper

Usage:
  cxpp launch [args...]      Launch Codex++ silent entry
  cxpp run [args...]         Alias of launch
  cxpp manager               Open Codex++ manager
  cxpp install-app           Install or repair local entrypoints
  cxpp repair-app            Alias of install-app
  cxpp doctor [--json]       Inspect local state
  cxpp version               Print wrapper version
`);
}

async function runLauncher(args = [], options = {}) {
  const command = args[0];
  if (!command || command === 'help' || command === '--help' || command === '-h') {
    printHelp();
    return { status: 0 };
  }
  if (command === 'version' || command === '--version' || command === '-V') {
    console.log(packageVersion(options));
    return { status: 0 };
  }
  if (command === 'doctor') {
    return { status: printDoctor(args.includes('--json'), options) };
  }
  if (command === 'install-app' || command === 'repair-app' || command === 'setup' || command === 'repair' || command === 'npm-postinstall') {
    const supported = SUPPORTED_PLATFORMS.has(platformKey(optionValue(options, 'platform', process.platform), optionValue(options, 'arch', process.arch)));
    if (!supported) {
      const message = t('unsupportedPlatform', options.env || process.env);
      console.log(`install_mode=unsupported`);
      console.log(`message=${message}`);
      if (command === 'npm-postinstall') {
        return { status: 0 };
      }
      return { status: 1, error: new Error(message) };
    }
    const result = await installApp(options);
    console.log(`install_mode=sidecar`);
    console.log(`upstream_version=${bundledUpstreamVersion(options) || 'missing'}`);
    console.log(`install_root=${result.installed.installRoot}`);
    console.log(`silent_binary=${result.installed.silent}`);
    console.log(`manager_binary=${result.installed.manager}`);
    console.log(`entrypoints=${result.entrypoints.skipped ? 'skipped' : 'installed'}`);
    return { status: 0 };
  }
  if (command === 'launch' || command === 'run') {
    const passthrough = args.slice(1);
    return spawnSidecar('silent', passthrough[0] === '--' ? passthrough.slice(1) : passthrough, options);
  }
  if (command === 'manager') {
    return spawnSidecar('manager', args.slice(1), options);
  }
  return spawnSidecar('silent', args, options);
}

module.exports = {
  SUPPORTED_PLATFORMS,
  bundledSidecarPath,
  bundledUpstreamVersion,
  copyReplacingChangedFile,
  defaultInstallRoot,
  doctorReport,
  executableName,
  filesMatch,
  findRunningProcessesForPath,
  installApp,
  installEntrypoints,
  installSidecars,
  installMacEntrypoints,
  installSidecarRoot,
  installWindowsEntrypoints,
  detectedInstallRoot,
  installedSidecarPath,
  isPermissionError,
  fallbackMacInstallRoot,
  macAppRoot,
  platformKey,
  promptYesNoWindowsPopup,
  removePath,
  runLauncher,
  spawnSidecar,
  terminateProcesses,
  upstreamBinDir,
  upstreamMetadata,
  upstreamMetadataPath,
  windowsShortcutScript,
  windowsEntrypointPaths,
  writeMacAppBundle,
};
