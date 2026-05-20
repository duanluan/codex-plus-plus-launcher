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
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '0.1.11' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.3', commit: '84c3e597' }));
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
          assert.equal(report.package_version, '0.1.11');
          assert.equal(report.upstream_version, 'v1.1.3');
          assert.equal(report.upstream_commit, '84c3e597');
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
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '0.1.11' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.3' }));
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
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '0.1.11' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'darwin-arm64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.3' }));
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


def test_unsupported_linux_postinstall_is_nonfatal_but_launch_fails():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-linux-'));
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '0.1.11' }));
        fs.mkdirSync(path.join(root, 'upstream-bin'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.3' }));

        (async () => {
          const postinstall = await launcher.runLauncher(['npm-postinstall'], {
            packageRoot: root,
            platform: 'linux',
            arch: 'x64',
            env: {},
          });
          assert.equal(postinstall.status, 0);

          assert.throws(
            () => launcher.spawnSidecar('silent', [], { packageRoot: root, platform: 'linux', arch: 'x64', env: {} }),
            { code: 'CODEXPP_UNSUPPORTED_PLATFORM' },
          );
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )
