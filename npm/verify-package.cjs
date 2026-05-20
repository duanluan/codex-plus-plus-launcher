#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const REQUIRED_PLATFORMS = {
  'win32-x64': ['codex-plus-plus.exe', 'codex-plus-plus-manager.exe'],
  'darwin-x64': ['codex-plus-plus', 'codex-plus-plus-manager'],
  'darwin-arm64': ['codex-plus-plus', 'codex-plus-plus-manager'],
};

const REQUIRED_ICONS = {
  'win32-x64': 'codex-plus-plus.ico',
  'darwin-x64': 'codex-plus-plus.png',
  'darwin-arm64': 'codex-plus-plus.png',
};

function packageRoot() {
  return path.resolve(__dirname, '..');
}

function upstreamBinRoot(root = packageRoot()) {
  return path.join(root, 'upstream-bin');
}

function verifyUpstreamMetadata(root = packageRoot()) {
  const expected = path.join(upstreamBinRoot(root), 'upstream-release.json');
  if (!fs.existsSync(expected)) {
    throw new Error(`missing required upstream release metadata: ${expected}`);
  }
  const payload = JSON.parse(fs.readFileSync(expected, 'utf8'));
  if (!payload.version && !payload.tag && !payload.upstream_version) {
    throw new Error(`upstream release metadata does not contain a version: ${expected}`);
  }
  return expected;
}

function verifyBundledSidecars(root = packageRoot()) {
  const verified = [];
  for (const [platform, names] of Object.entries(REQUIRED_PLATFORMS)) {
    for (const name of names) {
      const expected = path.join(upstreamBinRoot(root), platform, name);
      if (!fs.existsSync(expected)) {
        throw new Error(`missing required bundled upstream sidecar: ${expected}`);
      }
      verified.push(expected);
    }
  }
  return verified;
}

function verifyBundledIcon(root = packageRoot()) {
  const verified = [];
  for (const [platform, name] of Object.entries(REQUIRED_ICONS)) {
    const expected = path.join(upstreamBinRoot(root), platform, name);
    if (!fs.existsSync(expected)) {
      throw new Error(`missing required bundled icon asset: ${expected}`);
    }
    verified.push(expected);
  }
  return verified;
}

function main() {
  const metadata = verifyUpstreamMetadata();
  const sidecars = verifyBundledSidecars();
  const icons = verifyBundledIcon();
  console.log(`verified upstream metadata: ${metadata}`);
  console.log(`verified bundled upstream sidecars: ${sidecars.length}`);
  console.log(`verified bundled icons: ${icons.length}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message || String(error));
    process.exit(1);
  }
}

module.exports = { REQUIRED_ICONS, REQUIRED_PLATFORMS, main, upstreamBinRoot, verifyBundledIcon, verifyBundledSidecars, verifyUpstreamMetadata };
