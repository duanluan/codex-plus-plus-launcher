#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function packageRoot() {
  return path.resolve(__dirname, '..');
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', shell: false, ...options });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function platformKey(platform = process.platform, arch = process.arch) {
  return `${platform}-${arch}`;
}

function buildTargetArgs(key) {
  if (key === 'darwin-x64') {
    return ['--target', 'x86_64-apple-darwin'];
  }
  if (key === 'darwin-arm64') {
    return ['--target', 'aarch64-apple-darwin'];
  }
  if (key === 'linux-x64') {
    return [];
  }
  return [];
}

function cargoTargetForKey(key) {
  const args = buildTargetArgs(key);
  return args.length ? args[1] : '';
}

function packageBuildArgs(key) {
  return key === 'linux-x64' ? ['-p', 'codex-plus-launcher'] : [];
}

function main() {
  const root = packageRoot();
  const upstreamDir = process.env.CODEXPP_UPSTREAM_DIR || path.join(os.tmpdir(), 'CodexPlusPlus-upstream-build');
  const ref = process.env.CODEXPP_UPSTREAM_REF || 'v1.1.3';
  const key = process.env.CODEXPP_SIDECAR_PLATFORM || platformKey();
  const outDir = path.join(root, 'upstream-bin', key);

  if (!fs.existsSync(upstreamDir)) {
    run('git', ['clone', '--depth', '1', '--branch', ref, 'https://github.com/BigPizzaV3/CodexPlusPlus.git', upstreamDir], { cwd: root });
  } else {
    run('git', ['fetch', '--depth', '1', 'origin', ref], { cwd: upstreamDir });
    run('git', ['checkout', 'FETCH_HEAD'], { cwd: upstreamDir });
  }

  if (key !== 'linux-x64') {
    run('npm', ['install', '--package-lock=false'], { cwd: path.join(upstreamDir, 'apps', 'codex-plus-manager'), shell: process.platform === 'win32' });
    run('npm', ['run', 'vite:build'], { cwd: path.join(upstreamDir, 'apps', 'codex-plus-manager'), shell: process.platform === 'win32' });
  }
  run('cargo', ['build', '--release', ...buildTargetArgs(key), ...packageBuildArgs(key)], { cwd: upstreamDir });

  const cargoTarget = cargoTargetForKey(key);
  const targetDir = path.join(upstreamDir, 'target', ...(cargoTarget ? [cargoTarget] : []), 'release');
  fs.mkdirSync(outDir, { recursive: true });
  const exe = key.startsWith('win32') ? '.exe' : '';
  fs.copyFileSync(path.join(targetDir, `codex-plus-plus${exe}`), path.join(outDir, `codex-plus-plus${exe}`));
  const managerSource = path.join(targetDir, `codex-plus-plus-manager${exe}`);
  if (fs.existsSync(managerSource)) {
    fs.copyFileSync(managerSource, path.join(outDir, `codex-plus-plus-manager${exe}`));
  }
  const iconSource = key.startsWith('darwin')
    ? path.join(upstreamDir, 'apps', 'codex-plus-manager', 'src-tauri', 'icons', 'icon.png')
    : path.join(upstreamDir, 'apps', 'codex-plus-manager', 'src-tauri', 'icons', 'icon.ico');
  if (fs.existsSync(iconSource)) {
    fs.copyFileSync(iconSource, path.join(outDir, key.startsWith('darwin') ? 'codex-plus-plus.png' : 'codex-plus-plus.ico'));
  }

  const cargoToml = fs.readFileSync(path.join(upstreamDir, 'Cargo.toml'), 'utf8');
  const versionMatch = cargoToml.match(/^\s*version\s*=\s*"([^"]+)"/m);
  const version = versionMatch ? versionMatch[1] : JSON.parse(fs.readFileSync(path.join(upstreamDir, 'apps', 'codex-plus-manager', 'package.json'), 'utf8')).version;
  const commit = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: upstreamDir, encoding: 'utf8' }).stdout.trim();
  fs.mkdirSync(path.join(root, 'upstream-bin'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'upstream-bin', 'upstream-release.json'),
    JSON.stringify({ version: `v${version}`, commit, repository: 'BigPizzaV3/CodexPlusPlus', ref }, null, 2) + '\n',
    'utf8',
  );
  console.log(`built upstream sidecars: ${outDir}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message || String(error));
    process.exit(1);
  }
}

module.exports = { buildTargetArgs, cargoTargetForKey, main, packageBuildArgs, platformKey };
