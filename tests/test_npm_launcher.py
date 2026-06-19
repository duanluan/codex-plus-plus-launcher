from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def assert_node_ok(script: str) -> None:
    result = run_node(script)
    assert result.returncode == 0, result.stderr or result.stdout


def test_dispatcher_launch_manager_doctor_and_install_app():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-package-'));
        const installRoot = path.join(root, 'install');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7', commit: '333c2b0c' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'silent-v1');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'manager-v1');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');

        const spawned = [];
        const options = {
          packageRoot: root,
          installRoot,
          platform: 'win32',
          arch: 'x64',
          desktopDir: path.join(root, 'Desktop'),
          startMenuDir: path.join(root, 'Start Menu', 'Codex++'),
          env: { APPDATA: path.join(root, 'AppData'), LOCALAPPDATA: path.join(root, 'Local') },
          spawnSync(command, args, childOptions) {
            spawned.push({ command, args, childOptions });
            return { status: 0, stdout: '', stderr: '' };
          },
        };

        (async () => {
          const install = await launcher.runLauncher(['install-app'], options);
          assert.equal(install.status, 0);
          assert.equal(fs.readFileSync(path.join(installRoot, 'codex-plus-plus.exe'), 'utf8'), 'silent-v1');
          assert.equal(fs.readFileSync(path.join(installRoot, 'codex-plus-plus-manager.exe'), 'utf8'), 'manager-v1');
          assert.equal(spawned.length, 1);
          assert.match(spawned[0].args.at(-1), /Codex\+\+ 管理工具\.lnk/);
          assert.match(spawned[0].args.at(-1), /codex-plus-plus-manager\.exe/);

          const launch = await launcher.runLauncher(['launch', '--', '--debug-port', '9229'], options);
          assert.equal(launch.status, 0);
          assert.equal(spawned.at(-1).command, path.join(installRoot, 'codex-plus-plus.exe'));
          assert.deepEqual(spawned.at(-1).args, ['--debug-port', '9229']);

          const manager = await launcher.runLauncher(['manager'], options);
          assert.equal(manager.status, 0);
          assert.equal(spawned.at(-1).command, path.join(installRoot, 'codex-plus-plus-manager.exe'));

          const report = launcher.doctorReport(options);
          assert.equal(report.package_version, '1.2.0');
          assert.equal(report.upstream_version, 'v1.1.7');
          assert.equal(report.upstream_commit, '333c2b0c');
          assert.equal(report.supported, 'yes');
          assert.equal(report.silent_binary_state, 'installed');
          assert.equal(report.manager_binary_state, 'installed');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_install_sidecars_replaces_same_path_when_contents_change():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-replace-'));
        const installRoot = path.join(root, 'install');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'new-silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'new-manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');
        fs.mkdirSync(installRoot, { recursive: true });
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus.exe'), 'old-silent');
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus-manager.exe'), 'old-manager');

        (async () => {
          await launcher.installSidecars({ packageRoot: root, installRoot, platform: 'win32', arch: 'x64' });
          assert.equal(fs.readFileSync(path.join(installRoot, 'codex-plus-plus.exe'), 'utf8'), 'new-silent');
          assert.equal(fs.readFileSync(path.join(installRoot, 'codex-plus-plus-manager.exe'), 'utf8'), 'new-manager');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_windows_shortcut_plan_includes_two_entries_in_two_locations():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const installRoot = 'C:\\Users\\me\\AppData\\Local\\Programs\\Codex++';
        const scripts = [];
        const fakeFs = {
          mkdirSync() {},
        };
        launcher.installWindowsEntrypoints(
          {
            silent: path.join(installRoot, 'codex-plus-plus.exe'),
            manager: path.join(installRoot, 'codex-plus-plus-manager.exe'),
          },
          {
            fs: fakeFs,
            platform: 'win32',
            desktopDir: 'C:\\Users\\me\\Desktop',
            startMenuDir: 'C:\\Users\\me\\Start Menu\\Codex++',
            spawnSync(command, args) {
              assert.equal(command, 'powershell.exe');
              scripts.push(args.at(-1));
              return { status: 0, stdout: '', stderr: '' };
            },
          },
        );

        assert.equal(scripts.length, 1);
        const script = scripts[0];
        assert.match(script, /Codex\+\+\.lnk/);
        assert.match(script, /Codex\+\+ 管理工具\.lnk/);
        assert.match(script, /codex-plus-plus\.exe/);
        assert.match(script, /codex-plus-plus-manager\.exe/);
        assert.equal((script.match(/\$Shortcut\.Save\(\)/g) || []).length, 4);
        """
    )


def test_macos_app_bundle_falls_back_to_user_applications():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-macos-'));
        const fallbackRoot = path.join(root, 'home', 'Applications');
        const installRoot = path.join(root, 'Applications');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'darwin-arm64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'darwin-arm64', 'codex-plus-plus'), 'silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'darwin-arm64', 'codex-plus-plus-manager'), 'manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'darwin-arm64', 'codex-plus-plus.png'), 'png');

        const realFs = fs;
        const fakeFs = {
          ...fs,
          mkdirSync(candidate, opts) {
            if (candidate === installRoot) {
              const error = new Error('denied');
              error.code = 'EACCES';
              throw error;
            }
            return realFs.mkdirSync(candidate, opts);
          },
          accessSync(candidate) {
            if (candidate === installRoot) {
              const error = new Error('denied');
              error.code = 'EACCES';
              throw error;
            }
            return realFs.accessSync(candidate, fs.constants.W_OK);
          },
        };

        (async () => {
          const result = await launcher.installApp({
            fs: fakeFs,
            packageRoot: root,
            installRoot,
            fallbackInstallRoot: fallbackRoot,
            platform: 'darwin',
            arch: 'arm64',
          });
          assert.equal(result.installed.installRoot, fallbackRoot);
          assert.equal(result.entrypoints.appRoot, fallbackRoot);
          assert.ok(fs.existsSync(path.join(fallbackRoot, 'Codex++.app', 'Contents', 'MacOS', 'CodexPlusPlus')));
          assert.ok(fs.existsSync(path.join(fallbackRoot, 'Codex++ 管理工具.app', 'Contents', 'MacOS', 'CodexPlusPlusManager')));
          const plist = fs.readFileSync(path.join(fallbackRoot, 'Codex++.app', 'Contents', 'Info.plist'), 'utf8');
          assert.match(plist, /<key>LSUIElement<\/key>\s*<true\/>/);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_linux_codex_desktop_install_creates_shim_and_entrypoint():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const { spawnSync } = require('node:child_process');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-linux-'));
        const home = path.join(root, 'home');
        const xdgData = path.join(root, 'xdg-data');
        const xdgState = path.join(root, 'xdg-state');
        const installRoot = path.join(root, 'install');
        const codexApp = path.join(root, 'opt', 'codex-desktop');
        fs.mkdirSync(path.join(codexApp, 'content', 'webview', 'assets'), { recursive: true });
        fs.writeFileSync(
          path.join(codexApp, 'start.sh'),
          [
            '#!/usr/bin/env bash',
            'set -euo pipefail',
            'SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"',
            'cat "$SCRIPT_DIR/content/webview/assets/plugin-auth-abcd.js" > "$CODEXPP_PLUGIN_RESULT"',
            'printf "%s\\n" "$SCRIPT_DIR" > "$CODEXPP_PLUGIN_ROOT_RESULT"',
            '',
          ].join('\n'),
        );
        fs.writeFileSync(path.join(codexApp, 'content', 'webview', 'index.html'), '<html></html>');
        fs.writeFileSync(path.join(codexApp, 'content', 'webview', 'assets', 'plugin-auth-abcd.js'), 'locked');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'npm'), { recursive: true });
        fs.writeFileSync(path.join(root, 'npm', 'plugin-auth-unlocked.js'), 'function e(e){return false}export{e as t};\n');
        fs.mkdirSync(path.join(root, 'upstream-bin', 'linux-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'linux-x64', 'codex-plus-plus'), 'silent');

        (async () => {
          const install = await launcher.runLauncher(['install-app'], {
            packageRoot: root,
            installRoot,
            platform: 'linux',
            arch: 'x64',
            homeDir: home,
            env: {
              XDG_DATA_HOME: xdgData,
              XDG_STATE_HOME: xdgState,
              CODEXPP_LINUX_CODEX_START: path.join(codexApp, 'start.sh'),
            },
          });
          assert.equal(install.status, 0);
          assert.equal(fs.readFileSync(path.join(installRoot, 'codex-plus-plus'), 'utf8'), 'silent');

          const shim = path.join(xdgData, 'Codex++', 'codex-desktop-linux-shim', 'codex.exe');
          assert.ok(fs.existsSync(shim));
          const shimContent = fs.readFileSync(shim, 'utf8');
          assert.match(shimContent, /plugin-auth-\*\.js/);
          assert.match(shimContent, /content\/webview\/assets/);
          assert.match(shimContent, /"\$TMP_APP_ROOT\/start\.sh" -- "\$@"/);
          assert.equal(
            fs.readFileSync(path.join(xdgData, 'Codex++', 'codex-desktop-linux-shim', 'plugin-auth-unlocked.js'), 'utf8'),
            'function e(e){return false}export{e as t};\n',
          );

          const pluginResult = path.join(root, 'plugin-result.txt');
          const pluginRootResult = path.join(root, 'plugin-root-result.txt');
          const execResult = spawnSync(shim, [], {
            encoding: 'utf8',
            env: {
              ...process.env,
              CODEXPP_PLUGIN_RESULT: pluginResult,
              CODEXPP_PLUGIN_ROOT_RESULT: pluginRootResult,
            },
          });
          assert.equal(execResult.status, 0, execResult.stderr || execResult.stdout);
          assert.equal(fs.readFileSync(pluginResult, 'utf8'), 'function e(e){return false}export{e as t};\n');
          assert.notEqual(fs.readFileSync(pluginRootResult, 'utf8').trim(), codexApp);

          const entry = path.join(xdgData, 'applications', 'codex-plus-plus.desktop');
          assert.ok(fs.existsSync(entry));
          assert.match(fs.readFileSync(entry, 'utf8'), /Name=Codex\+\+/);
          assert.match(fs.readFileSync(entry, 'utf8'), /--app-path/);

          const report = launcher.doctorReport({
            packageRoot: root,
            installRoot,
            platform: 'linux',
            arch: 'x64',
            homeDir: home,
            env: {
              XDG_DATA_HOME: xdgData,
              XDG_STATE_HOME: xdgState,
              CODEXPP_LINUX_CODEX_START: path.join(codexApp, 'start.sh'),
            },
          });
          assert.equal(report.supported, 'yes');
          assert.equal(report.manager_binary_state, 'unsupported');
          assert.equal(report.manager_entrypoint_state, 'unsupported');
          assert.equal(report.linux_codex_desktop_state, 'found');
          assert.equal(report.linux_codex_shim_state, 'installed');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_linux_postinstall_is_nonfatal_when_codex_desktop_missing():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-linux-missing-'));
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'linux-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'linux-x64', 'codex-plus-plus'), 'silent');

        (async () => {
          const postinstall = await launcher.runLauncher(['npm-postinstall'], {
            packageRoot: root,
            platform: 'linux',
            arch: 'x64',
            homeDir: path.join(root, 'home'),
            env: {},
          });
          assert.equal(postinstall.status, 0);

          await assert.rejects(
            () => launcher.runLauncher(['install-app'], {
              packageRoot: root,
              platform: 'linux',
              arch: 'x64',
              homeDir: path.join(root, 'home'),
              env: {},
            }),
            { code: 'CODEXPP_MISSING_LINUX_CODEX_DESKTOP' },
          );
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_linux_appimage_appdir_detection_creates_shim():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-linux-appdir-'));
        const appDir = path.join(root, 'AppDir');
        const start = path.join(appDir, 'opt', 'codex-desktop', 'start.sh');
        fs.mkdirSync(path.dirname(start), { recursive: true });
        fs.writeFileSync(start, '#!/usr/bin/env bash\n');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'linux-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'linux-x64', 'codex-plus-plus'), 'silent');

        (async () => {
          const result = await launcher.installApp({
            packageRoot: root,
            installRoot: path.join(root, 'install'),
            platform: 'linux',
            arch: 'x64',
            homeDir: path.join(root, 'home'),
            env: {
              XDG_DATA_HOME: path.join(root, 'xdg-data'),
              XDG_STATE_HOME: path.join(root, 'xdg-state'),
              APPDIR: appDir,
            },
            which() {
              return '';
            },
          });
          assert.equal(result.linux.startScript, start);
          assert.ok(fs.existsSync(path.join(root, 'xdg-data', 'Codex++', 'codex-desktop-linux-shim', 'codex.exe')));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_install_sidecars_writes_version_stamp():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-stamp-'));
        const installRoot = path.join(root, 'install');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.16' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');

        (async () => {
          await launcher.installSidecars({ packageRoot: root, installRoot, platform: 'win32', arch: 'x64' });
          const stamp = fs.readFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8');
          assert.equal(stamp.trim(), '1.2.16');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_install_sidecars_refreshes_version_stamp_on_upgrade():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-stamp-upgrade-'));
        const installRoot = path.join(root, 'install');
        fs.mkdirSync(installRoot, { recursive: true });
        fs.writeFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.16' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');

        (async () => {
          await launcher.installSidecars({ packageRoot: root, installRoot, platform: 'win32', arch: 'x64' });
          const stamp = fs.readFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8');
          assert.equal(stamp.trim(), '1.2.16');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_install_sidecars_stamp_failure_is_nonfatal():
    # Best-effort stamp: if the filesystem rejects the write, postinstall must not crash.
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-stamp-nonfatal-'));
        const installRoot = path.join(root, 'install');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.16' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');

        const stampPath = path.join(installRoot, launcher.SIDECAR_VERSION_STAMP);
        const fakeFs = {
          ...fs,
          writeFileSync(target, data, options) {
            if (target === stampPath) {
              const error = new Error('locked');
              error.code = 'EBUSY';
              throw error;
            }
            return fs.writeFileSync(target, data, options);
          },
        };

        (async () => {
          const result = await launcher.installSidecars({
            fs: fakeFs,
            packageRoot: root,
            installRoot,
            platform: 'win32',
            arch: 'x64',
          });
          assert.equal(result.installRoot, installRoot);
          assert.ok(fs.existsSync(path.join(installRoot, 'codex-plus-plus.exe')));
          assert.ok(!fs.existsSync(stampPath));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_linux_launch_uses_silent_sidecar_and_auto_app_path():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-linux-launch-'));
        const installRoot = path.join(root, 'install');
        const home = path.join(root, 'home');
        const xdgData = path.join(root, 'xdg-data');
        const xdgState = path.join(root, 'xdg-state');
        const codexApp = path.join(root, 'opt', 'codex-desktop');
        fs.mkdirSync(codexApp, { recursive: true });
        fs.writeFileSync(path.join(codexApp, 'start.sh'), '#!/usr/bin/env bash\n');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.0' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'linux-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'linux-x64', 'codex-plus-plus'), 'silent');
        fs.mkdirSync(installRoot, { recursive: true });
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus'), 'silent');

        const spawned = [];
        (async () => {
          const launch = await launcher.runLauncher(['launch', '--', '--app-path', path.join(root, 'shim')], {
            packageRoot: root,
            installRoot,
            platform: 'linux',
            arch: 'x64',
            homeDir: home,
            env: {
              XDG_DATA_HOME: xdgData,
              XDG_STATE_HOME: xdgState,
            },
            which() {
              return '';
            },
            spawnSync(command, args) {
              spawned.push({ command, args });
              return { status: 0, stdout: '', stderr: '' };
            },
          });
          assert.equal(launch.status, 0);
          assert.equal(spawned[0].command, path.join(installRoot, 'codex-plus-plus'));
          assert.deepEqual(spawned[0].args, ['--app-path', path.join(root, 'shim')]);

          const implicit = await launcher.runLauncher(['launch', '--new-chat'], {
            packageRoot: root,
            installRoot,
            platform: 'linux',
            arch: 'x64',
            homeDir: home,
            env: {
              XDG_DATA_HOME: xdgData,
              XDG_STATE_HOME: xdgState,
              CODEXPP_LINUX_CODEX_START: path.join(codexApp, 'start.sh'),
            },
            which() {
              return '';
            },
            spawnSync(command, args) {
              spawned.push({ command, args });
              return { status: 0, stdout: '', stderr: '' };
            },
          });
          assert.equal(implicit.status, 0);
          assert.equal(spawned[1].command, path.join(installRoot, 'codex-plus-plus'));
          assert.deepEqual(spawned[1].args, ['--app-path', path.join(xdgData, 'Codex++', 'codex-desktop-linux-shim'), '--new-chat']);
          assert.ok(fs.existsSync(path.join(xdgData, 'Codex++', 'codex-desktop-linux-shim', 'codex.exe')));

          const manager = await launcher.runLauncher(['manager'], {
            packageRoot: root,
            installRoot,
            platform: 'linux',
            arch: 'x64',
            env: {},
            spawnSync() {
              throw new Error('manager should not spawn');
            },
          });
          assert.equal(manager.status, 1);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )
