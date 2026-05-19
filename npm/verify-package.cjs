#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function packageRoot() {
  return path.resolve(__dirname, '..');
}

function platformBinaryName(platform = process.platform, arch = process.arch) {
  const extension = platform === 'win32' ? '.exe' : '';
  return `cxpp-${platform}-${arch}${extension}`;
}

function verifyCurrentPlatformBinary() {
  const root = packageRoot();
  const expected = path.join(root, 'bin', platformBinaryName());
  if (!fs.existsSync(expected)) {
    throw new Error(`missing required bundled binary for ${process.platform}/${process.arch}: ${expected}`);
  }
  return expected;
}

function verifyBundledIcon() {
  const root = packageRoot();
  const expected = path.join(root, 'codex_plus_plus_launcher', 'assets', 'codex-plus-plus.ico');
  if (!fs.existsSync(expected)) {
    throw new Error(`missing required bundled icon asset: ${expected}`);
  }
  return expected;
}

function main() {
  const target = verifyCurrentPlatformBinary();
  const icon = verifyBundledIcon();
  console.log(`verified bundled binary: ${target}`);
  console.log(`verified bundled icon: ${icon}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message || String(error));
    process.exit(1);
  }
}

module.exports = { main, platformBinaryName, verifyBundledIcon, verifyCurrentPlatformBinary };
