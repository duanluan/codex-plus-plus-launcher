const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const { spawn, spawnSync } = require('node:child_process');
const { t } = require('./i18n.js');

const SUPPORTED_PLATFORMS = new Set(['win32-x64', 'darwin-x64', 'darwin-arm64', 'linux-x64']);
const SILENT_BINARY = 'codex-plus-plus';
const MANAGER_BINARY = 'codex-plus-plus-manager';
const SIDECAR_VERSION_STAMP = '.codexpp-sidecar-version';
const SILENT_NAME = 'Codex++';
const MANAGER_NAME = 'Codex++ 管理工具';
const LINUX_SHIM_DIR_NAME = 'codex-desktop-linux-shim';
const LINUX_SHIM_BINARY = 'codex.exe';
const LINUX_DESKTOP_ENTRY = 'codex-plus-plus.desktop';
const PLUGIN_AUTH_UNLOCK_FILE = 'plugin-auth-unlocked.js';
const PLUGIN_AUTH_UNLOCK_CONTENT = 'function e(e){return false}export{e as t};\n';

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

function requiredSidecarKinds(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  return platform === 'linux' ? ['silent'] : ['silent', 'manager'];
}

function sidecarKindSupported(kind, options = {}) {
  return requiredSidecarKinds(options).includes(kind);
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

function pluginAuthUnlockPath(options = {}) {
  const root = optionValue(options, 'packageRoot', packageRoot);
  return optionValue(options, 'pluginAuthUnlockPath', () => path.join(root, 'npm', PLUGIN_AUTH_UNLOCK_FILE));
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
  const missing = requiredSidecarKinds(options).map((kind) => bundledSidecarPath(kind, options)).filter((candidate) => !fsImpl.existsSync(candidate));
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

function xdgDataHome(options = {}) {
  const env = options.env || process.env;
  return env.XDG_DATA_HOME || path.join(optionValue(options, 'homeDir', () => os.homedir()), '.local', 'share');
}

function xdgStateHome(options = {}) {
  const env = options.env || process.env;
  return env.XDG_STATE_HOME || path.join(optionValue(options, 'homeDir', () => os.homedir()), '.local', 'state');
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

function linuxShimRoot(options = {}) {
  return optionValue(options, 'linuxShimRoot', () => path.join(xdgDataHome(options), 'Codex++', LINUX_SHIM_DIR_NAME));
}

function linuxEntrypointPath(options = {}) {
  return optionValue(options, 'linuxEntrypointPath', () => path.join(xdgDataHome(options), 'applications', LINUX_DESKTOP_ENTRY));
}

function linuxInstallStatePath(options = {}) {
  return optionValue(options, 'linuxInstallStatePath', () => path.join(xdgStateHome(options), 'codex-plus-plus-launcher', 'linux-install.json'));
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
  for (const kind of requiredSidecarKinds(options)) {
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
  try {
    fsImpl.writeFileSync(
      path.join(installRoot, SIDECAR_VERSION_STAMP),
      packageVersion(options) + '\n',
    );
  } catch (_error) {
    // Stamp is best-effort; doctor will fall back to platform probes.
  }
  installed.installRoot = installRoot;
  return installed;
}

function readInstalledSidecarVersion(options = {}) {
  const fsImpl = options.fs || fs;
  const platform = optionValue(options, 'platform', process.platform);
  const installRoot = optionValue(options, 'installRoot', () => detectedInstallRoot(options));
  const stampPath = path.join(installRoot, SIDECAR_VERSION_STAMP);
  try {
    const raw = fsImpl.readFileSync(stampPath, 'utf8');
    const first = String(raw).split(/\r?\n/)[0].trim();
    if (first) {
      return first;
    }
  } catch (_error) {
    // stamp absent or unreadable; fall through to platform probe
  }
  if (platform !== 'win32') {
    return null;
  }
  const silent = installedSidecarPath('silent', { ...options, installRoot });
  if (!fsImpl.existsSync(silent)) {
    return null;
  }
  const run = options.spawnSync || spawnSync;
  try {
    const result = run(
      'powershell',
      ['-NoProfile', '-NonInteractive', '-Command', '(Get-Item -LiteralPath $args[0]).VersionInfo.FileVersion', '--', silent],
      { encoding: 'utf8', windowsHide: true },
    );
    if (result && result.status === 0) {
      const out = String(result.stdout || '').trim();
      if (out) {
        return out;
      }
    }
  } catch (_error) {
    // probe failed; treat as unknown
  }
  return null;
}

function computeSidecarDrift(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const arch = optionValue(options, 'arch', process.arch);
  if (!SUPPORTED_PLATFORMS.has(platformKey(platform, arch))) {
    return 'unsupported';
  }
  const fsImpl = options.fs || fs;
  const installRoot = optionValue(options, 'installRoot', () => detectedInstallRoot(options));
  const silent = installedSidecarPath('silent', { ...options, installRoot });
  if (!fsImpl.existsSync(silent)) {
    return 'mismatch';
  }
  const bundled = packageVersion(options);
  const installed = readInstalledSidecarVersion({ ...options, installRoot });
  if (!installed) {
    return 'unknown';
  }
  return installed === bundled ? 'none' : 'mismatch';
}

async function ensureSidecarsFresh(options = {}) {
  const drift = computeSidecarDrift(options);
  if (drift === 'none' || drift === 'unsupported') {
    return { action: 'noop', drift };
  }
  const env = options.env || process.env;
  const before = readInstalledSidecarVersion(options);
  const after = packageVersion(options);
  const stderr = options.stderr || process.stderr;
  try {
    await installSidecars({
      ...options,
      promptYesNo: () => false,
      promptYesNoWindowsPopup: () => false,
    });
    const arrow = before ? `${before} -> ${after}` : `-> ${after}`;
    stderr.write(`${t('sidecarSelfHealOk', env)} (${arrow})\n`);
    return { action: 'reinstalled', drift, before, after };
  } catch (error) {
    if (error && error.code === 'CODEXPP_LOCKED_OLD_BINARY') {
      stderr.write(`${t('sidecarSelfHealLocked', env)}\n`);
      return { action: 'locked', drift, error };
    }
    stderr.write(`${t('sidecarSelfHealFailed', env)}: ${(error && error.message) || String(error)}\n`);
    return { action: 'failed', drift, error };
  }
}

function normalizeExecutablePath(candidate) {
  return path.resolve(String(candidate || ''));
}

function linuxStartScriptFromBinary(binaryPath, options = {}) {
  const fsImpl = options.fs || fs;
  const normalized = normalizeExecutablePath(binaryPath);
  const basename = path.basename(normalized);
  const parent = path.dirname(normalized);
  const candidates = [];

  if (basename === 'start.sh') {
    candidates.push(normalized);
  }
  candidates.push(path.join(parent, 'start.sh'));
  if (basename === 'codex-desktop') {
    candidates.push('/opt/codex-desktop/start.sh');
    candidates.push(path.join(parent, '..', 'opt', 'codex-desktop', 'start.sh'));
    candidates.push(path.join(parent, '..', 'opt', 'codex-desktop-linux', 'lib', 'codex-desktop-linux', 'codex-app', 'start.sh'));
  }
  if (normalized.includes(`${path.sep}codex-desktop-linux${path.sep}`) || normalized.includes('/codex-desktop-linux/')) {
    candidates.push(path.join(parent, '..', 'lib', 'codex-desktop-linux', 'codex-app', 'start.sh'));
    candidates.push(path.join(parent, '..', 'codex-app', 'start.sh'));
  }

  for (const candidate of candidates) {
    const resolved = path.resolve(candidate);
    if (fsImpl.existsSync(resolved)) {
      return resolved;
    }
  }
  return null;
}

function linuxStartScriptCandidates(options = {}) {
  const env = options.env || process.env;
  const homeDir = optionValue(options, 'homeDir', () => os.homedir());
  const candidates = [];
  for (const value of [env.CODEXPP_LINUX_CODEX_START, env.CODEX_DESKTOP_LINUX_START, env.CODEX_DESKTOP_START]) {
    if (value) {
      candidates.push(value);
    }
  }
  for (const value of [env.CODEXPP_LINUX_APPDIR, env.CODEX_DESKTOP_LINUX_APPDIR, env.APPDIR]) {
    if (value) {
      candidates.push(path.join(value, 'opt', 'codex-desktop', 'start.sh'));
    }
  }
  for (const value of [env.CODEXPP_LINUX_CODEX_BIN, env.CODEX_DESKTOP_LINUX_BIN]) {
    if (value) {
      const start = linuxStartScriptFromBinary(value, options);
      if (start) {
        candidates.push(start);
      }
    }
  }
  const which = options.which || ((name) => {
    const result = (options.spawnSync || spawnSync)('which', [name], { encoding: 'utf8' });
    return result.status === 0 ? String(result.stdout || '').trim().split(/\r?\n/)[0] : '';
  });
  for (const name of ['codex-desktop', 'openai-codex-desktop']) {
    try {
      const found = which(name);
      if (found) {
        const start = linuxStartScriptFromBinary(found, options);
        if (start) {
          candidates.push(start);
        }
      }
    } catch (_error) {}
  }
  candidates.push('/opt/codex-desktop/start.sh');
  candidates.push(path.join(homeDir, '.local', 'opt', 'codex-desktop-linux', 'lib', 'codex-desktop-linux', 'codex-app', 'start.sh'));
  candidates.push(path.join(homeDir, 'codex-desktop-linux', 'codex-app', 'start.sh'));

  const unique = [];
  const seen = new Set();
  for (const candidate of candidates) {
    if (!candidate) {
      continue;
    }
    const resolved = path.resolve(candidate);
    if (!seen.has(resolved)) {
      seen.add(resolved);
      unique.push(resolved);
    }
  }
  return unique;
}

function detectLinuxCodexDesktop(options = {}) {
  const fsImpl = options.fs || fs;
  for (const startScript of linuxStartScriptCandidates(options)) {
    if (fsImpl.existsSync(startScript)) {
      const appRoot = path.dirname(startScript);
      return {
        kind: 'codex-desktop-linux',
        startScript,
        appRoot,
        resourcesDir: path.join(appRoot, 'resources'),
      };
    }
  }
  return null;
}

function shellSingleQuote(value) {
  return `'${String(value).replace(/'/g, "'\\''")}'`;
}

function linuxCodexShimScript(startScript, pluginAuthUnlockFile) {
  return [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    '',
    `START_SCRIPT=${shellSingleQuote(startScript)}`,
    `PLUGIN_AUTH_UNLOCK_FILE=${shellSingleQuote(pluginAuthUnlockFile)}`,
    'TMP_APP_ROOT=""',
    'CHILD_PID=""',
    '',
    'resolve_file_dir() {',
    '  local source="$1"',
    '  local dir',
    '  while [ -L "$source" ]; do',
    '    dir="$(cd -P "$(dirname "$source")" && pwd)"',
    '    source="$(readlink "$source")"',
    '    case "$source" in',
    '      /*) ;;',
    '      *) source="$dir/$source" ;;',
    '    esac',
    '  done',
    '  cd -P "$(dirname "$source")" && pwd',
    '}',
    '',
    'cleanup() {',
    '  if [ -n "$TMP_APP_ROOT" ]; then',
    '    rm -rf "$TMP_APP_ROOT"',
    '  fi',
    '}',
    '',
    'forward_signal() {',
    '  local sig="$1"',
    '  if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then',
    '    kill -"$sig" "$CHILD_PID" 2>/dev/null || true',
    '  fi',
    '}',
    '',
    'trap cleanup EXIT',
    "trap 'forward_signal HUP' HUP",
    "trap 'forward_signal INT' INT",
    "trap 'forward_signal TERM' TERM",
    '',
    'APP_ROOT="$(resolve_file_dir "$START_SCRIPT")"',
    'WEBVIEW_DIR="$APP_ROOT/content/webview"',
    '',
    'if [ ! -f "$PLUGIN_AUTH_UNLOCK_FILE" ]; then',
    '  echo "Codex++ plugin auth unlock file not found: $PLUGIN_AUTH_UNLOCK_FILE" >&2',
    '  exit 1',
    'fi',
    '',
    'if [ ! -d "$WEBVIEW_DIR" ]; then',
    '  exec "$START_SCRIPT" -- "$@"',
    'fi',
    '',
    'TMP_APP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/codex-plus-plus-linux-app.XXXXXX")"',
    'cp "$START_SCRIPT" "$TMP_APP_ROOT/start.sh"',
    'chmod 755 "$TMP_APP_ROOT/start.sh"',
    '',
    'shopt -s dotglob nullglob',
    'for entry in "$APP_ROOT"/*; do',
    '  name="$(basename "$entry")"',
    '  if [ "$name" = "start.sh" ] || [ "$name" = "content" ]; then',
    '    continue',
    '  fi',
    '  ln -s "$entry" "$TMP_APP_ROOT/$name"',
    'done',
    'shopt -u dotglob nullglob',
    '',
    'mkdir -p "$TMP_APP_ROOT/content/webview/assets"',
    'if [ -d "$APP_ROOT/content" ]; then',
    '  shopt -s dotglob nullglob',
    '  for entry in "$APP_ROOT/content"/*; do',
    '    name="$(basename "$entry")"',
    '    if [ "$name" = "webview" ]; then',
    '      continue',
    '    fi',
    '    ln -s "$entry" "$TMP_APP_ROOT/content/$name"',
    '  done',
    '  shopt -u dotglob nullglob',
    'fi',
    '',
    'shopt -s dotglob nullglob',
    'for entry in "$WEBVIEW_DIR"/*; do',
    '  name="$(basename "$entry")"',
    '  if [ "$name" = "assets" ]; then',
    '    continue',
    '  fi',
    '  ln -s "$entry" "$TMP_APP_ROOT/content/webview/$name"',
    'done',
    'for entry in "$WEBVIEW_DIR/assets"/*; do',
    '  name="$(basename "$entry")"',
    '  if [[ "$name" == plugin-auth-*.js ]]; then',
    '    ln -s "$PLUGIN_AUTH_UNLOCK_FILE" "$TMP_APP_ROOT/content/webview/assets/$name"',
    '  else',
    '    ln -s "$entry" "$TMP_APP_ROOT/content/webview/assets/$name"',
    '  fi',
    'done',
    'shopt -u dotglob nullglob',
    '',
    '"$TMP_APP_ROOT/start.sh" -- "$@" &',
    'CHILD_PID=$!',
    'set +e',
    'wait "$CHILD_PID"',
    'STATUS=$?',
    'set -e',
    'CHILD_PID=""',
    'exit "$STATUS"',
    '',
  ].join('\n');
}

function writeLinuxCodexShim(installation, options = {}) {
  const fsImpl = options.fs || fs;
  const shimRoot = linuxShimRoot(options);
  fsImpl.mkdirSync(shimRoot, { recursive: true });
  const shimPath = path.join(shimRoot, LINUX_SHIM_BINARY);
  const pluginAuthTarget = path.join(shimRoot, PLUGIN_AUTH_UNLOCK_FILE);
  const pluginAuthSource = pluginAuthUnlockPath(options);
  if (fsImpl.existsSync(pluginAuthSource)) {
    fsImpl.copyFileSync(pluginAuthSource, pluginAuthTarget);
  } else {
    fsImpl.writeFileSync(pluginAuthTarget, PLUGIN_AUTH_UNLOCK_CONTENT, 'utf8');
  }
  fsImpl.writeFileSync(shimPath, linuxCodexShimScript(installation.startScript, pluginAuthTarget), 'utf8');
  fsImpl.chmodSync(shimPath, 0o755);
  return { shimRoot, shimPath, pluginAuthUnlock: pluginAuthTarget };
}

function linuxDesktopEntry({ name, execPath, iconPath, comment }) {
  const iconLine = iconPath ? `Icon=${iconPath}\n` : '';
  return `[Desktop Entry]
Name=${name}
Comment=${comment}
Exec=${execPath}
${iconLine}Terminal=false
Type=Application
Categories=Development;
StartupNotify=true
`;
}

function installLinuxEntrypoints(installed, options = {}) {
  const fsImpl = options.fs || fs;
  const desktopPath = linuxEntrypointPath(options);
  fsImpl.mkdirSync(path.dirname(desktopPath), { recursive: true });
  const command = `${desktopExecArg(installed.silent)} --app-path ${desktopExecArg(installed.linuxShimRoot)}`;
  fsImpl.writeFileSync(
    desktopPath,
    linuxDesktopEntry({
      name: SILENT_NAME,
      execPath: command,
      iconPath: installed.icon || '',
      comment: 'Launch Codex++ with Codex Desktop for Linux',
    }),
    'utf8',
  );
  return {
    silent: desktopPath,
    manager: 'unsupported',
  };
}

function desktopExecArg(value) {
  const raw = String(value);
  if (/^[A-Za-z0-9_/:=.,@%+-]+$/.test(raw)) {
    return raw.replace(/%/g, '%%');
  }
  return `"${raw.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/`/g, '\\`').replace(/\$/g, '\\$').replace(/%/g, '%%')}"`;
}

function linuxShellArg(value) {
  const raw = String(value);
  if (/^[A-Za-z0-9_/:=.,@%+-]+$/.test(raw)) {
    return raw;
  }
  return shellSingleQuote(raw);
}

function linuxHasExplicitAppPath(args) {
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--app-path' && args[index + 1]) {
      return true;
    }
  }
  return false;
}

function linuxShimPathFromRoot(root) {
  return path.join(root, LINUX_SHIM_BINARY);
}

function linuxStateShimRoots(state) {
  const roots = [];
  if (state && state.codex_shim_root) {
    roots.push(state.codex_shim_root);
  }
  if (state && state.codex_shim) {
    roots.push(path.dirname(state.codex_shim));
  }
  return roots;
}

function ensureLinuxCodexShimRoot(options = {}) {
  const fsImpl = options.fs || fs;
  const state = readJsonFile(linuxInstallStatePath(options), fsImpl) || {};
  const roots = [...linuxStateShimRoots(state), linuxShimRoot(options)];
  const seen = new Set();
  for (const root of roots) {
    if (!root || seen.has(root)) {
      continue;
    }
    seen.add(root);
    if (fsImpl.existsSync(linuxShimPathFromRoot(root))) {
      return root;
    }
  }

  const installation = detectLinuxCodexDesktop(options);
  if (!installation) {
    return null;
  }
  const shim = writeLinuxCodexShim(installation, options);
  const installedSilent = installedSidecarPath('silent', options);
  const silent = fsImpl.existsSync(installedSilent) ? installedSilent : bundledSidecarPath('silent', options);
  writeLinuxInstallState(
    {
      silent,
      installRoot: path.dirname(silent),
      linuxShim: shim.shimPath,
      linuxShimRoot: shim.shimRoot,
    },
    installation,
    options,
  );
  return shim.shimRoot;
}

function linuxSilentLaunchArgs(args, options = {}) {
  if (linuxHasExplicitAppPath(args)) {
    return args;
  }
  const shimRoot = ensureLinuxCodexShimRoot(options);
  if (!shimRoot) {
    const error = new Error(t('missingLinuxCodexDesktop', options.env || process.env));
    error.code = 'CODEXPP_MISSING_LINUX_CODEX_DESKTOP';
    throw error;
  }
  return ['--app-path', shimRoot, ...args];
}

function writeLinuxInstallState(installed, installation, options = {}) {
  const fsImpl = options.fs || fs;
  const statePath = linuxInstallStatePath(options);
  fsImpl.mkdirSync(path.dirname(statePath), { recursive: true });
  const payload = {
    mode: 'codex_desktop_linux',
    app_integration_state: 'installed',
    codex_desktop_linux_start: installation.startScript,
    codex_desktop_linux_app_root: installation.appRoot,
    codex_shim: installed.linuxShim,
    codex_shim_root: installed.linuxShimRoot,
    silent_binary: installed.silent,
    upstream_version: bundledUpstreamVersion(options) || null,
    installed_at: new Date().toISOString(),
  };
  fsImpl.writeFileSync(statePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
  return statePath;
}

async function installLinuxApp(options = {}) {
  const installation = detectLinuxCodexDesktop(options);
  if (!installation) {
    const error = new Error(t('missingLinuxCodexDesktop', options.env || process.env));
    error.code = 'CODEXPP_MISSING_LINUX_CODEX_DESKTOP';
    throw error;
  }
  const installed = await installSidecars(options);
  const shim = writeLinuxCodexShim(installation, options);
  installed.linuxShim = shim.shimPath;
  installed.linuxShimRoot = shim.shimRoot;
  installed.linuxPluginAuthUnlock = shim.pluginAuthUnlock;
  installed.linuxCodexStart = installation.startScript;
  const entrypoints = await installEntrypoints(installed, { ...options, installRoot: installed.installRoot });
  const statePath = writeLinuxInstallState(installed, installation, options);
  return { installed, entrypoints, linux: installation, statePath };
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
  if (platform === 'linux') {
    return installLinuxEntrypoints(installed, options);
  }
  return { unsupported: true };
}

async function installApp(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  if (platform === 'linux') {
    return installLinuxApp(options);
  }
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
  if (platform === 'linux') {
    const desktopPath = linuxEntrypointPath(options);
    return {
      silent: fsImpl.existsSync(desktopPath) ? 'installed' : 'missing',
      manager: 'unsupported',
      silent_path: desktopPath,
      manager_path: '',
    };
  }
  return { silent: 'unsupported', manager: 'unsupported' };
}

function installedSidecars(options = {}) {
  const fsImpl = options.fs || fs;
  const silent = installedSidecarPath('silent', options);
  const manager = installedSidecarPath('manager', options);
  const managerSupported = sidecarKindSupported('manager', options);
  return {
    silent,
    manager,
    silent_state: fsImpl.existsSync(silent) ? 'installed' : 'missing',
    manager_state: managerSupported ? (fsImpl.existsSync(manager) ? 'installed' : 'missing') : 'unsupported',
  };
}

function doctorReport(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const arch = optionValue(options, 'arch', process.arch);
  const installRoot = optionValue(options, 'installRoot', () => detectedInstallRoot(options));
  const sidecars = installedSidecars(options);
  const entrypoints = inspectEntrypoints(options);
  const supported = SUPPORTED_PLATFORMS.has(platformKey(platform, arch));
  const report = {
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
  if (platform === 'linux') {
    const linux = detectLinuxCodexDesktop(options);
    const state = readJsonFile(linuxInstallStatePath(options), options.fs || fs) || {};
    report.linux_codex_desktop_state = linux ? 'found' : 'missing';
    report.linux_codex_desktop_start = (linux && linux.startScript) || state.codex_desktop_linux_start || '';
    report.linux_codex_shim = state.codex_shim || path.join(linuxShimRoot(options), LINUX_SHIM_BINARY);
    report.linux_codex_shim_state = (options.fs || fs).existsSync(report.linux_codex_shim) ? 'installed' : 'missing';
    report.install_mode = state.mode || (linux ? 'codex_desktop_linux' : 'unsupported');
  }
  return report;
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
  if (platform === 'linux' && kind === 'manager') {
    return { status: 1, error: new Error(t('unsupportedLinuxManager', options.env || process.env)) };
  }
  if (platform === 'linux' && kind === 'silent') {
    try {
      args = linuxSilentLaunchArgs(args, options);
    } catch (error) {
      return { status: 1, error };
    }
  }
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
    let result;
    try {
      result = await installApp(options);
    } catch (error) {
      if (command === 'npm-postinstall' && error && error.code === 'CODEXPP_MISSING_LINUX_CODEX_DESKTOP') {
        console.log(`install_mode=unsupported`);
        console.log(`message=${error.message || String(error)}`);
        return { status: 0 };
      }
      throw error;
    }
    console.log(`install_mode=sidecar`);
    console.log(`upstream_version=${bundledUpstreamVersion(options) || 'missing'}`);
    console.log(`install_root=${result.installed.installRoot}`);
    console.log(`silent_binary=${result.installed.silent}`);
    console.log(`manager_binary=${result.installed.manager || 'unsupported'}`);
    if (result.installed.linuxShim) {
      console.log(`linux_codex_shim=${result.installed.linuxShim}`);
      console.log(`linux_codex_desktop_start=${result.installed.linuxCodexStart}`);
    }
    console.log(`entrypoints=${result.entrypoints.skipped ? 'skipped' : 'installed'}`);
    return { status: 0 };
  }
  if (command === 'launch' || command === 'run') {
    await ensureSidecarsFresh(options);
    const passthrough = args.slice(1);
    return spawnSidecar('silent', passthrough[0] === '--' ? passthrough.slice(1) : passthrough, options);
  }
  if (command === 'manager') {
    await ensureSidecarsFresh(options);
    return spawnSidecar('manager', args.slice(1), options);
  }
  await ensureSidecarsFresh(options);
  return spawnSidecar('silent', args, options);
}

module.exports = {
  SIDECAR_VERSION_STAMP,
  SUPPORTED_PLATFORMS,
  bundledSidecarPath,
  bundledUpstreamVersion,
  computeSidecarDrift,
  copyReplacingChangedFile,
  defaultInstallRoot,
  doctorReport,
  ensureSidecarsFresh,
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
  readInstalledSidecarVersion,
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
