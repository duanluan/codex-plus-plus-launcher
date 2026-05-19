#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', shell: false, ...options });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function findPackedTarball(root) {
  const { name, version } = require(path.join(root, 'package.json'));
  const tarballName = name.startsWith('@') ? name.slice(1).replace('/', '-') : name;
  const expectedName = `${tarballName}-${version}.tgz`;
  const tarball = path.join(root, expectedName);
  if (!fs.existsSync(tarball)) {
    throw new Error(`no packed npm tarball found for ${name}@${version}; run \`npm pack\` first`);
  }
  return tarball;
}

function main() {
  const root = path.resolve(__dirname, '..');
  const tarball = findPackedTarball(root);
  const prefix = path.join(os.tmpdir(), `cxpp-npm-smoke-${Date.now()}`);
  fs.mkdirSync(prefix, { recursive: true });

  const pathValue = process.env.PATH || process.env.Path || '';
  const pathKey = process.platform === 'win32' ? 'Path' : 'PATH';
  const commandDir = process.platform === 'win32' ? prefix : path.join(prefix, 'bin');
  const env = {
    ...process.env,
    [pathKey]: pathValue ? `${commandDir}${path.delimiter}${pathValue}` : commandDir,
    npm_config_prefix: prefix,
    CODEXPP_SHORTCUT_MODE: 'skip',
  };
  run('npm', ['i', '-g', tarball], { cwd: root, env, shell: true });

  const cmd = process.platform === 'win32' ? path.join(prefix, 'cxpp.cmd') : path.join(prefix, 'bin', 'cxpp');
  if (!fs.existsSync(cmd)) {
    throw new Error(`smoke install did not produce cxpp command: ${cmd}`);
  }

  run(cmd, ['version'], { cwd: root, env, shell: process.platform === 'win32' });
  run(cmd, ['doctor'], { cwd: root, env, shell: process.platform === 'win32' });
  console.log(`smoke install passed with prefix: ${prefix}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message || String(error));
    process.exit(1);
  }
}

module.exports = { main };
