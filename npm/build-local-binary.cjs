#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function packageRoot() {
  return path.resolve(__dirname, '..');
}

function platformBinaryName(platform = process.platform, arch = process.arch) {
  const extension = platform === 'win32' ? '.exe' : '';
  return `cxpp-${platform}-${arch}${extension}`;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', shell: false, ...options });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function main() {
  const root = packageRoot();
  const python = process.env.CODEXPP_BUILD_PYTHON || 'python';
  const vendorDir = path.join(root, '.build-tools');
  const distDir = path.join(root, 'dist');
  const binDir = path.join(root, 'bin');
  const binaryName = platformBinaryName();
  const distBinary = path.join(distDir, binaryName);
  const finalBinary = path.join(binDir, binaryName);
  const releaseInfoPath = path.join(root, '.build-tools', 'upstream-release.json');
  const iconData = `codex_plus_plus_launcher${path.sep}assets${path.sep}codex-plus-plus.ico${path.delimiter}codex_plus_plus_launcher${path.sep}assets`;
  const upstreamReleaseData = `${releaseInfoPath}${path.delimiter}codex_plus_plus_launcher`;

  fs.mkdirSync(vendorDir, { recursive: true });
  fs.mkdirSync(binDir, { recursive: true });

  run(python, ['-m', 'pip', 'install', '--target', vendorDir, 'pyinstaller'], { cwd: root });
  run(python, ['-c', `from codex_plus_plus_launcher.upstream_release import write_latest_release_json; write_latest_release_json(r"${releaseInfoPath.replace(/\\/g, '\\\\')}")`], { cwd: root });
  const releaseInfo = JSON.parse(fs.readFileSync(releaseInfoPath, 'utf8'));
  if (!releaseInfo.install_spec) {
    throw new Error('failed to resolve latest upstream release install spec');
  }
  run(python, ['-m', 'pip', 'install', '--target', vendorDir, releaseInfo.install_spec], { cwd: root });

  const env = {
    ...process.env,
    PYTHONPATH: process.env.PYTHONPATH ? `${root}${path.delimiter}${vendorDir}${path.delimiter}${process.env.PYTHONPATH}` : `${root}${path.delimiter}${vendorDir}`,
  };

  run(
    python,
    [
      '-m',
      'PyInstaller',
      '--onefile',
      '--collect-all',
      'codex_session_delete',
      '--add-data',
      iconData,
      '--add-data',
      upstreamReleaseData,
      '--name',
      path.parse(binaryName).name,
      'codex_plus_plus_launcher/__main__.py',
    ],
    { cwd: root, env },
  );

  if (!fs.existsSync(distBinary)) {
    throw new Error(`PyInstaller did not produce expected binary: ${distBinary}`);
  }

  fs.copyFileSync(distBinary, finalBinary);
  console.log(`built local binary: ${finalBinary}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message || String(error));
    process.exit(1);
  }
}

module.exports = { main, platformBinaryName };
