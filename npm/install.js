#!/usr/bin/env node

const { t } = require('./i18n.js');
const { installGlobalBinary, runLauncher } = require('./launcher.js');

async function main() {
  if (process.env.CODEXPP_SKIP_NPM_POSTINSTALL === '1') {
    return;
  }

  const args = ['npm-postinstall'];

  console.log(t('installingCodexPlusPlus'));
  try {
    await installGlobalBinary();
  } catch (error) {
    if (process.env.CODEXPP_ALLOW_PYTHON_FALLBACK !== '1' || error.code === 'CODEXPP_LOCKED_OLD_BINARY') {
      throw error;
    }
  }
  const result = runLauncher(args);
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
