#!/usr/bin/env node

const { main } = require('./npm/install.js');

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
