#!/usr/bin/env node

const { spawnSync } = require('node:child_process');
const { t } = require('./i18n.js');
const { runLauncher } = require('./launcher.js');

function main(args = process.argv.slice(2)) {
  const result = runLauncher(args);
  if (result.error) {
    console.error(result.error.message || String(result.error));
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

if (require.main === module) {
  main();
}
