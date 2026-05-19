const fs = require('node:fs');
const { copyFileSync, chmodSync, existsSync, mkdirSync } = fs;
const { spawnSync } = require('node:child_process');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const { t } = require('./i18n.js');

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

function platformBinaryName(platform = process.platform, arch = process.arch) {
  const extension = platform === 'win32' ? '.exe' : '';
  return `cxpp-${platform}-${arch}${extension}`;
}

function packageRoot() {
  return path.resolve(__dirname, '..');
}

function packageVersion() {
  return require(path.join(packageRoot(), 'package.json')).version;
}

function bundledBinaryPath(options = {}) {
  const env = options.env || process.env;
  const platform = optionValue(options, 'platform', process.platform);
  const arch = optionValue(options, 'arch', process.arch);
  if (env.CODEXPP_BINARY) {
    return env.CODEXPP_BINARY;
  }
  return path.join(packageRoot(), 'bin', platformBinaryName(platform, arch));
}

function globalPrefix(options = {}) {
  const env = options.env || process.env;
  if (env.npm_config_prefix) {
    return env.npm_config_prefix;
  }
  return path.resolve(packageRoot(), '..', '..', '..');
}

function globalBinaryPath(options = {}) {
  const platform = optionValue(options, 'platform', process.platform);
  const arch = optionValue(options, 'arch', process.arch);
  const version = optionValue(options, 'packageVersion', packageVersion);
  const prefix = optionValue(options, 'globalPrefix', () => globalPrefix(options));
  const extension = platform === 'win32' ? '.exe' : '';
  const name = `cxpp-native-${version}-${platform}-${arch}${extension}`;
  return path.join(prefix, name);
}

function preferredBinaryPath() {
  if (process.env.CODEXPP_BINARY) {
    return process.env.CODEXPP_BINARY;
  }
  const globalBinary = globalBinaryPath();
  if (existsSync(globalBinary)) {
    return globalBinary;
  }
  return bundledBinaryPath();
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
      fsImpl.rmSync(candidate, { force: true });
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

async function removeStaleGlobalBinary(candidate, target, options = {}) {
  const fsImpl = options.fs || fs;
  const platform = optionValue(options, 'platform', process.platform);
  try {
    fsImpl.rmSync(candidate, { force: true });
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

async function installGlobalBinary(options = {}) {
  const fsImpl = options.fs || fs;
  const source = optionValue(options, 'bundledBinaryPath', () => bundledBinaryPath(options));
  if (!fsImpl.existsSync(source)) {
    throw new Error(`${t('missingBinary')}: ${source}`);
  }

  const target = optionValue(options, 'globalBinaryPath', () => globalBinaryPath(options));
  fsImpl.mkdirSync(path.dirname(target), { recursive: true });
  if (!fsImpl.existsSync(target)) {
    fsImpl.copyFileSync(source, target);
    fsImpl.chmodSync(target, 0o755);
  }
  const prefix = optionValue(options, 'globalPrefix', () => globalPrefix(options));
  for (const entry of fsImpl.readdirSync(prefix, { withFileTypes: true })) {
    if (!entry.isFile()) {
      continue;
    }
    if (!/^cxpp-native-.*-win32-x64\.exe$/i.test(entry.name)) {
      continue;
    }
    const candidate = path.join(prefix, entry.name);
    if (path.resolve(candidate) === path.resolve(target)) {
      continue;
    }
    await removeStaleGlobalBinary(candidate, target, options);
  }
  return target;
}

function findPython() {
  if (process.env.CODEXPP_PYTHON) {
    return process.env.CODEXPP_PYTHON;
  }
  for (const candidate of ['python3', 'python', 'py']) {
    const result = spawnSync(candidate, ['--version'], { stdio: 'ignore' });
    if (result.status === 0) {
      return candidate;
    }
  }
  return null;
}

function pythonEnv(env = process.env) {
  const root = packageRoot();
  return {
    ...env,
    PYTHONPATH: env.PYTHONPATH ? `${root}${path.delimiter}${env.PYTHONPATH}` : root,
  };
}

function runLauncher(args, options = {}) {
  const cwd = options.cwd || os.homedir();
  const binary = preferredBinaryPath();
  if (existsSync(binary)) {
    return spawnSync(binary, args, { stdio: 'inherit', cwd, env: process.env });
  }

  if (process.env.CODEXPP_ALLOW_PYTHON_FALLBACK === '1') {
    const python = findPython();
    if (!python) {
      return { status: 1, error: new Error(t('missingPython')) };
    }
    const moduleName = process.env.CODEXPP_WRAPPER_MODULE || 'codex_plus_plus_launcher';
    return spawnSync(python, ['-m', moduleName, ...args], {
      stdio: 'inherit',
      cwd,
      env: pythonEnv(),
    });
  }

  return { status: 1, error: new Error(`${t('missingBinary')}: ${binary}`) };
}

module.exports = {
  bundledBinaryPath,
  findRunningProcessesForPath,
  globalBinaryPath,
  installGlobalBinary,
  isPermissionError,
  platformBinaryName,
  promptYesNoWindowsPopup,
  removeStaleGlobalBinary,
  runLauncher,
  terminateProcesses,
};
