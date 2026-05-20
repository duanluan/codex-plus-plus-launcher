#!/usr/bin/env node

const { runLauncher } = require('./launcher.js');

async function main(args = process.argv.slice(2)) {
  const result = await runLauncher(args);
  if (result.error) {
    console.error(result.error.message || String(result.error));
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message || String(error));
    process.exit(1);
  });
}

module.exports = { main };
