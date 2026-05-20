#!/usr/bin/env node

const { t } = require('./i18n.js');
const { runLauncher } = require('./launcher.js');

async function main() {
  if (process.env.CODEXPP_SKIP_NPM_POSTINSTALL === '1') {
    return;
  }

  const args = ['npm-postinstall'];

  console.log(t('installingCodexPlusPlus'));
  const result = await runLauncher(args);
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${t('runningCommandFailed')}: cxpp ${args.join(' ')}`);
  }
  console.log(t('installDone'));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message || String(error));
    process.exit(1);
  });
}

module.exports = { main };
