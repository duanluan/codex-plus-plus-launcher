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


def test_prepack_rejects_bundled_upstream_version_mismatch():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const verify = require('./npm/verify-package.cjs');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-verify-version-'));
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.30' }));
        fs.mkdirSync(path.join(root, 'upstream-bin'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.2.15' }));

        assert.throws(
          () => verify.verifyUpstreamMetadata(root),
          /bundled upstream version v1\.2\.15 does not match package version 1\.2\.30/
        );

        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.2.30' }));
        assert.equal(verify.verifyUpstreamMetadata(root), path.join(root, 'upstream-bin', 'upstream-release.json'));
        """
    )


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
          assert.equal(report.expected_sidecar_version, '1.2.0');
          assert.equal(report.installed_sidecar_version, '1.2.0');
          assert.equal(report.sidecar_drift, 'none');
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
        const launcherScripts = [];
        const fakeFs = {
          mkdirSync() {},
          writeFileSync(target, contents) {
            launcherScripts.push({ target, contents });
          },
        };
        launcher.installWindowsEntrypoints(
          {
            silent: path.join(installRoot, 'codex-plus-plus.exe'),
            manager: path.join(installRoot, 'codex-plus-plus-manager.exe'),
          },
          {
            fs: fakeFs,
            platform: 'win32',
            packageRoot: 'C:\\Users\\me\\AppData\\Roaming\\npm\\node_modules\\@duanluan\\codex-plus-plus-launcher',
            nodePath: 'C:\\Program Files\\nodejs\\node.exe',
            env: { SystemRoot: 'C:\\Windows' },
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
        assert.equal(launcherScripts.length, 1);
        const script = scripts[0];
        assert.match(script, /Codex\+\+\.lnk/);
        assert.match(script, /Codex\+\+ 管理工具\.lnk/);
        assert.match(script, /wscript\.exe/);
        assert.match(script, /launch-codexpp\.vbs/);
        assert.match(script, /codex-plus-plus-manager\.exe/);
        assert.match(launcherScripts[0].contents, /cxpp\.js/);
        assert.match(launcherScripts[0].contents, /launch/);
        assert.equal((script.match(/\$Shortcut\.Save\(\)/g) || []).length, 4);
        """
    )


def test_windows_launch_restarts_codex_when_cdp_is_missing():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const spawned = [];
          const terminated = [];
          let terminatedByName = 0;
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{ ProcessId: 4321, Name: 'Codex.exe' }];
            },
            cdpTargetsAvailable(debugPort) {
              assert.equal(debugPort, 9229);
              return false;
            },
            findRunningSidecarProcesses() {
              return [];
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
            terminateSidecarsByImageName() {
              terminatedByName += 1;
              return true;
            },
            spawn(command, args) {
              spawned.push({ command, args });
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(terminated.map((processInfo) => processInfo.ProcessId), [4321]);
          assert.equal(terminatedByName, 1);
          assert.equal(spawned[0].command, path.join(fx.installRoot, 'codex-plus-plus.exe'));
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_launch_restarts_sidecar_only_when_cdp_is_missing():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-cdp-missing-sidecar-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const terminated = [];
          const spawned = [];
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{ ProcessId: 4321, Name: 'Codex.exe' }];
            },
            cdpTargetsAvailable(debugPort) {
              assert.equal(debugPort, 9229);
              return false;
            },
            findRunningSidecarProcesses() {
              return [{ ProcessId: 8765, Name: 'codex-plus-plus.exe' }];
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
            spawn(command, args) {
              spawned.push({ command, args });
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(terminated.map((processInfo) => processInfo.ProcessId), [4321, 8765]);
          assert.equal(spawned[0].command, path.join(fx.installRoot, 'codex-plus-plus.exe'));
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_launch_keeps_existing_codex_when_cdp_is_available():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-ok-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const terminated = [];
          const checkedPorts = [];
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{
                ProcessId: 4321,
                Name: 'Codex.exe',
                CommandLine: '"Codex.exe" --remote-debugging-port=55798',
              }];
            },
            cdpTargetsAvailable(debugPort) {
              checkedPorts.push(debugPort);
              return debugPort === 55798;
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
            spawn() {
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(checkedPorts, [55798]);
          assert.deepEqual(terminated, []);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_launch_keeps_existing_sidecar_when_menu_is_present():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-ui-present-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const terminated = [];
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{
                ProcessId: 4321,
                Name: 'Codex.exe',
                CommandLine: '"Codex.exe" --remote-debugging-port=55798',
              }];
            },
            cdpTargetsAvailable() {
              return true;
            },
            codexPlusUiInjectionState() {
              return 'present';
            },
            findRunningSidecarProcesses() {
              throw new Error('sidecar process lookup should not run when UI is present');
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
            spawn() {
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(terminated, []);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_launch_keeps_existing_processes_when_ui_probe_is_unknown():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-ui-unknown-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const terminated = [];
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{
                ProcessId: 4321,
                Name: 'Codex.exe',
                CommandLine: '"Codex.exe" --remote-debugging-port=55798',
              }];
            },
            cdpTargetsAvailable() {
              return true;
            },
            codexPlusUiInjectionState() {
              return 'unknown';
            },
            findRunningSidecarProcesses() {
              throw new Error('sidecar process lookup should not run when UI state is unknown');
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
            spawn() {
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(terminated, []);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_ui_injection_probe_supports_ipv6_loopback_cdp():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const { spawn } = require('node:child_process');
        const launcher = require('./npm/launcher.js');

        const serverSource = String.raw`
        const http = require('node:http');
        const crypto = require('node:crypto');

        function websocketAccept(key) {
          return crypto
            .createHash('sha1')
            .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
            .digest('base64');
        }

        function encodeServerTextFrame(text) {
          const payload = Buffer.from(text, 'utf8');
          const header = Buffer.alloc(payload.length < 126 ? 2 : 4);
          header[0] = 0x81;
          if (payload.length < 126) {
            header[1] = payload.length;
          } else {
            header[1] = 126;
            header.writeUInt16BE(payload.length, 2);
          }
          return Buffer.concat([header, payload]);
        }

        function firstClientTextFrame(buffer) {
          if (buffer.length < 6) return null;
          let length = buffer[1] & 0x7f;
          let offset = 2;
          if (length === 126) {
            if (buffer.length < 8) return null;
            length = buffer.readUInt16BE(2);
            offset = 4;
          }
          if (buffer.length < offset + 4 + length) return null;
          const mask = buffer.subarray(offset, offset + 4);
          offset += 4;
          const payload = Buffer.from(buffer.subarray(offset, offset + length));
          for (let index = 0; index < payload.length; index += 1) {
            payload[index] ^= mask[index % 4];
          }
          return JSON.parse(payload.toString('utf8'));
        }

        const server = http.createServer((req, res) => {
          if (req.url === '/json/list' || req.url === '/json') {
            res.setHeader('content-type', 'application/json');
            res.end(JSON.stringify([{
              type: 'page',
              webSocketDebuggerUrl: 'ws://[::1]:' + server.address().port + '/devtools/page/fixture',
            }]));
            return;
          }
          res.statusCode = 404;
          res.end();
        });

        server.on('upgrade', (req, socket) => {
          const key = req.headers['sec-websocket-key'];
          socket.write([
            'HTTP/1.1 101 Switching Protocols',
            'Upgrade: websocket',
            'Connection: Upgrade',
            'Sec-WebSocket-Accept: ' + websocketAccept(key),
            '',
            '',
          ].join('\r\n'));

          let buffer = Buffer.alloc(0);
          socket.on('data', (chunk) => {
            buffer = Buffer.concat([buffer, chunk]);
            const message = firstClientTextFrame(buffer);
            if (!message) return;
            socket.write(encodeServerTextFrame(JSON.stringify({
              id: message.id,
              result: { result: { type: 'boolean', value: true } },
            })));
          });
        });

        process.on('SIGTERM', () => server.close(() => process.exit(0)));
        server.listen({ host: '::1', port: 0 }, () => {
          console.log('PORT ' + server.address().port);
        });
        `;

        function waitForPort(child) {
          return new Promise((resolve, reject) => {
            let settled = false;
            let stdout = '';
            let stderr = '';
            const timer = setTimeout(() => {
              if (!settled) {
                settled = true;
                reject(new Error('CDP fixture server did not start: ' + stderr + stdout));
              }
            }, 5000);

            child.stdout.setEncoding('utf8');
            child.stdout.on('data', (chunk) => {
              stdout += chunk;
              const match = stdout.match(/PORT (\d+)/);
              if (match && !settled) {
                settled = true;
                clearTimeout(timer);
                resolve(Number(match[1]));
              }
            });
            child.stderr.setEncoding('utf8');
            child.stderr.on('data', (chunk) => {
              stderr += chunk;
            });
            child.on('exit', (code, signal) => {
              if (!settled) {
                settled = true;
                clearTimeout(timer);
                reject(new Error('CDP fixture server exited: ' + code + '/' + signal + ' ' + stderr));
              }
            });
          });
        }

        (async () => {
          const server = spawn(process.execPath, ['-e', serverSource], {
            stdio: ['ignore', 'pipe', 'pipe'],
            windowsHide: true,
          });
          const port = await waitForPort(server);
          try {
            const state = launcher.codexPlusUiInjectionState(port, {
              uiInjectionProbeTimeoutMs: 2000,
            });
            assert.equal(state, 'present');
          } finally {
            server.kill();
          }
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_launch_restarts_sidecar_when_cdp_is_available_but_menu_is_missing():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-ui-missing-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const terminated = [];
          const spawned = [];
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{
                ProcessId: 4321,
                Name: 'Codex.exe',
                CommandLine: '"Codex.exe" --remote-debugging-port=55798',
              }];
            },
            cdpTargetsAvailable(debugPort) {
              assert.equal(debugPort, 55798);
              return true;
            },
            codexPlusUiInjectionState(debugPort) {
              assert.equal(debugPort, 55798);
              return 'missing';
            },
            findRunningSidecarProcesses() {
              return [{ ProcessId: 8765, Name: 'codex-plus-plus.exe' }];
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
            spawn(command, args) {
              spawned.push({ command, args });
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(terminated.map((processInfo) => processInfo.ProcessId), [8765]);
          assert.equal(spawned[0].command, path.join(fx.installRoot, 'codex-plus-plus.exe'));
          assert.deepEqual(spawned[0].args, ['--debug-port', '55798']);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_launch_passes_existing_cdp_port_when_menu_is_missing_without_sidecar():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-preflight-ui-missing-port-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), fx.packageVersion + '\n');

          const spawned = [];
          let terminatedByName = 0;
          const result = await launcher.runLauncher(['launch'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningCodexProcesses() {
              return [{
                ProcessId: 4321,
                Name: 'Codex.exe',
                CommandLine: '"Codex.exe" --remote-debugging-port=9229',
              }];
            },
            cdpTargetsAvailable(debugPort) {
              assert.equal(debugPort, 9229);
              return true;
            },
            codexPlusUiInjectionState(debugPort) {
              assert.equal(debugPort, 9229);
              return 'missing';
            },
            findRunningSidecarProcesses() {
              return [];
            },
            terminateSidecarsByImageName() {
              terminatedByName += 1;
              return true;
            },
            terminateProcesses() {
              throw new Error('Codex should stay running when its CDP port is available');
            },
            spawn(command, args) {
              spawned.push({ command, args });
              return { once() {}, unref() {}, pid: 1234 };
            },
          });

          assert.equal(result.status, 0);
          assert.equal(terminatedByName, 1);
          assert.equal(spawned[0].command, path.join(fx.installRoot, 'codex-plus-plus.exe'));
          assert.deepEqual(spawned[0].args, ['--debug-port', '9229']);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_windows_terminate_processes_uses_taskkill_fallback():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');

        const calls = [];
        launcher.terminateProcesses(
          [{ ProcessId: 111, Name: 'codex-plus-plus.exe' }, { ProcessId: 111 }, { ProcessId: 222 }],
          {
            env: {},
            spawnSync(command, args, options) {
              calls.push({ command, args, options });
              return { status: 0, stdout: '', stderr: '' };
            },
          },
        );

        assert.equal(calls.length, 2);
        assert.equal(calls[0].command, 'powershell.exe');
        assert.equal(calls[0].options.env.CODEXPP_PROCESS_IDS, '111,222');
        assert.equal(calls[1].command, 'taskkill.exe');
        assert.deepEqual(calls[1].args, ['/F', '/PID', '111', '/PID', '222']);
      """
    )


def test_windows_terminate_sidecars_by_image_name_uses_taskkill_without_pid_lookup():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');

        const calls = [];
        const terminated = launcher.terminateSidecarsByImageName({
          platform: 'win32',
          env: {},
          spawnSync(command, args, options) {
            calls.push({ command, args, options });
            return { status: 0, stdout: '', stderr: '' };
          },
        });

        assert.equal(terminated, true);
        assert.equal(calls.length, 1);
        assert.equal(calls[0].command, 'taskkill.exe');
        assert.deepEqual(calls[0].args, ['/F', '/IM', 'codex-plus-plus.exe']);
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


def test_doctor_reports_windows_binary_version_over_stale_stamp():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-doctor-version-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-installed');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-installed');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');

          const report = launcher.doctorReport({
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            spawnSync(command, args, childOptions) {
              if (command === 'powershell.exe') {
                assert.equal(childOptions.env.CODEXPP_VERSION_PROBE_PATH, path.join(fx.installRoot, 'codex-plus-plus.exe'));
                return { status: 0, stdout: '1.2.15\n', stderr: '' };
              }
              return { status: 0, stdout: '', stderr: '' };
            },
          });

          assert.equal(report.expected_sidecar_version, '1.2.19');
          assert.equal(report.installed_sidecar_version, '1.2.15');
          assert.equal(report.sidecar_drift, 'mismatch');
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_stop_command_terminates_codex_plus_and_codex_processes_explicitly():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-stop-');
          const terminated = [];
          const result = await launcher.runLauncher(['stop'], {
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en' },
            findRunningSidecarProcesses() {
              return [{ ProcessId: 11, Name: 'codex-plus-plus.exe' }];
            },
            findRunningCodexPlusManagerProcesses() {
              return [{ ProcessId: 22, Name: 'codex-plus-plus-manager.exe' }];
            },
            findRunningCodexProcesses() {
              return [{ ProcessId: 33, Name: 'Codex.exe' }, { ProcessId: 44, Name: 'codex.exe' }];
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
            },
          });

          assert.equal(result.status, 0);
          assert.equal(result.stoppedCount, 4);
          assert.deepEqual(terminated.map((processInfo) => processInfo.ProcessId), [11, 22, 33, 44]);
        })().catch((error) => { console.error(error); process.exit(1); });
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
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.19' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');

        (async () => {
          await launcher.installSidecars({ packageRoot: root, installRoot, platform: 'win32', arch: 'x64' });
          const stamp = fs.readFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8');
          assert.equal(stamp.trim(), '1.2.19');
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
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.19' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');

        (async () => {
          await launcher.installSidecars({ packageRoot: root, installRoot, platform: 'win32', arch: 'x64' });
          const stamp = fs.readFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8');
          assert.equal(stamp.trim(), '1.2.19');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_install_sidecars_prompts_before_closing_locked_windows_binary():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-autoclose-'));
        const installRoot = path.join(root, 'install');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.19' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'new-silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'new-manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');
        fs.mkdirSync(installRoot, { recursive: true });
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus.exe'), 'old-silent');
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus-manager.exe'), 'old-manager');

        const lockedTarget = path.join(installRoot, 'codex-plus-plus.exe');
        const terminated = [];
        let locked = true;
        const prompts = [];
        const fakeFs = {
          ...fs,
          rmSync(target, options) {
            if (path.resolve(target) === path.resolve(lockedTarget) && locked) {
              const error = new Error('EPERM: locked');
              error.code = 'EPERM';
              throw error;
            }
            return fs.rmSync(target, options);
          },
        };

        (async () => {
          await launcher.installSidecars({
            fs: fakeFs,
            packageRoot: root,
            installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en', CODEXPP_ENABLE_WINDOWS_PROMPT: '1' },
            findRunningProcessesForPath(candidate) {
              if (path.resolve(candidate) === path.resolve(lockedTarget)) {
                return [{ ProcessId: 1234, Name: 'codex-plus-plus.exe', ExecutablePath: candidate }];
              }
              return [];
            },
            promptYesNoWindowsPopup(question) {
              prompts.push(question);
              return true;
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
              locked = false;
            },
            spawnSync() {
              return { status: 0, stdout: '', stderr: '' };
            },
          });

          assert.deepEqual(terminated.map((processInfo) => processInfo.ProcessId), [1234]);
          assert.equal(prompts.length, 1);
          assert.equal(fs.readFileSync(lockedTarget, 'utf8'), 'new-silent');
          assert.equal(fs.readFileSync(path.join(installRoot, 'codex-plus-plus-manager.exe'), 'utf8'), 'new-manager');
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_npm_postinstall_prompts_before_closing_locked_windows_sidecar():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');

        const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cxpp-postinstall-locked-'));
        const installRoot = path.join(root, 'install');
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.19' }));
        fs.mkdirSync(path.join(root, 'upstream-bin', 'win32-x64'), { recursive: true });
        fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.exe'), 'new-silent');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus-manager.exe'), 'new-manager');
        fs.writeFileSync(path.join(root, 'upstream-bin', 'win32-x64', 'codex-plus-plus.ico'), 'icon');
        fs.mkdirSync(installRoot, { recursive: true });
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus.exe'), 'old-silent');
        fs.writeFileSync(path.join(installRoot, 'codex-plus-plus-manager.exe'), 'old-manager');
        fs.writeFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');

        const lockedTarget = path.join(installRoot, 'codex-plus-plus.exe');
        const terminated = [];
        let locked = true;
        const prompts = [];
        const fakeFs = {
          ...fs,
          rmSync(target, options) {
            if (path.resolve(target) === path.resolve(lockedTarget) && locked) {
              const error = new Error('EPERM: locked');
              error.code = 'EPERM';
              throw error;
            }
            return fs.rmSync(target, options);
          },
        };

        (async () => {
          const result = await launcher.runLauncher(['npm-postinstall'], {
            fs: fakeFs,
            packageRoot: root,
            installRoot,
            platform: 'win32',
            arch: 'x64',
            env: { CODEXPP_LANG: 'en', CODEXPP_ENABLE_WINDOWS_PROMPT: '1' },
            findRunningProcessesForPath(candidate) {
              if (path.resolve(candidate) === path.resolve(lockedTarget)) {
                return [{ ProcessId: 1234, Name: 'codex-plus-plus.exe', ExecutablePath: candidate }];
              }
              return [];
            },
            promptYesNoWindowsPopup(question) {
              prompts.push(question);
              return true;
            },
            terminateProcesses(processes) {
              terminated.push(...processes);
              locked = false;
            },
            spawnSync() {
              return { status: 0, stdout: '', stderr: '' };
            },
          });

          assert.equal(result.status, 0);
          assert.deepEqual(terminated.map((processInfo) => processInfo.ProcessId), [1234]);
          assert.equal(prompts.length, 1);
          assert.equal(fs.readFileSync(lockedTarget, 'utf8'), 'new-silent');
          assert.equal(fs.readFileSync(path.join(installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8').trim(), '1.2.19');
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
        fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: '1.2.19' }));
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


SELF_HEAL_FIXTURE = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const launcher = require('./npm/launcher.js');

function makeFixture(prefix, opts) {
  opts = opts || {};
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  const installRoot = path.join(root, 'install');
  const platform = opts.platform || 'win32';
  const arch = opts.arch || 'x64';
  const platDir = platform + '-' + arch;
  const packageVersion = opts.packageVersion || '1.2.19';
  fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ version: packageVersion }));
  fs.mkdirSync(path.join(root, 'upstream-bin', platDir), { recursive: true });
  fs.writeFileSync(path.join(root, 'upstream-bin', 'upstream-release.json'), JSON.stringify({ version: 'v1.1.7' }));
  const exeSuffix = platform === 'win32' ? '.exe' : '';
  fs.writeFileSync(path.join(root, 'upstream-bin', platDir, 'codex-plus-plus' + exeSuffix), 'silent-bundled');
  if (platform !== 'linux') {
    fs.writeFileSync(path.join(root, 'upstream-bin', platDir, 'codex-plus-plus-manager' + exeSuffix), 'manager-bundled');
  }
  fs.writeFileSync(path.join(root, 'upstream-bin', platDir, 'codex-plus-plus.ico'), 'icon');
  return { root: root, installRoot: installRoot, platform: platform, arch: arch, packageVersion: packageVersion };
}

function captureStderr() {
  const chunks = [];
  return {
    stream: { write: function(s) { chunks.push(String(s)); return true; } },
    text: function() { return chunks.join(''); },
  };
}
"""


def test_self_heal_noop_when_drift_is_none():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-none-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-bundled');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-bundled');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.19\n');

          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
          });
          assert.equal(result.action, 'noop');
          assert.equal(result.drift, 'none');
          assert.equal(stderr.text(), '');
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_reinstalls_on_mismatch():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-mismatch-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-old');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-old');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');

          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
          });
          assert.equal(result.action, 'reinstalled');
          assert.equal(result.drift, 'mismatch');
          assert.equal(result.before, '1.2.5');
          assert.equal(result.after, '1.2.19');
          assert.equal(fs.readFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'utf8'), 'silent-bundled');
          assert.equal(fs.readFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8').trim(), '1.2.19');
          assert.match(stderr.text(), /refreshed the local sidecar/);
          assert.match(stderr.text(), /1\.2\.5 -> 1\.2\.19/);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_reinstalls_on_unknown_when_stamp_missing():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-unknown-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-mystery');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-mystery');
          // No stamp file. spawnSync override forces the PE-version probe to "fail".

          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
            spawnSync: () => ({ status: 1, stdout: '', stderr: '' }),
          });
          assert.equal(result.action, 'reinstalled');
          assert.equal(result.drift, 'unknown');
          assert.equal(result.before, null);
          assert.equal(result.after, '1.2.19');
          assert.equal(fs.readFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8').trim(), '1.2.19');
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_reinstalls_when_sidecar_file_missing():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-missing-');
          // installRoot does not exist yet; drift = mismatch (no silent file).
          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
          });
          assert.equal(result.action, 'reinstalled');
          assert.equal(result.drift, 'mismatch');
          assert.ok(fs.existsSync(path.join(fx.installRoot, 'codex-plus-plus.exe')));
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_handles_locked_old_binary_softly():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-locked-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-old');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-old');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');

          const realFs = fs;
          const lockedTarget = path.join(fx.installRoot, 'codex-plus-plus.exe');
          const fakeFs = Object.assign({}, realFs, {
            rmSync: function(target, options) {
              if (path.resolve(target) === lockedTarget) {
                const err = new Error('EPERM: locked');
                err.code = 'EPERM';
                throw err;
              }
              return realFs.rmSync(target, options);
            },
          });

          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            fs: fakeFs,
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
            findRunningProcessesForPath: () => [{ ProcessId: 1234, Name: 'codex-plus-plus.exe' }],
            terminateProcesses: () => {},
          });
          assert.equal(result.action, 'locked');
          assert.equal(result.drift, 'mismatch');
          assert.ok(result.error);
          assert.equal(result.error.code, 'CODEXPP_LOCKED_OLD_BINARY');
          assert.match(stderr.text(), /currently running/);
          assert.equal(fs.readFileSync(lockedTarget, 'utf8'), 'silent-old');
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_falls_back_softly_on_other_failures():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-fail-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-old');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-old');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');

          const realFs = fs;
          const fakeFs = Object.assign({}, realFs, {
            copyFileSync: function() {
              const err = new Error('ENOSPC: disk full');
              err.code = 'ENOSPC';
              throw err;
            },
          });

          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            fs: fakeFs,
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'win32',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
          });
          assert.equal(result.action, 'failed');
          assert.equal(result.drift, 'mismatch');
          assert.ok(result.error);
          assert.equal(result.error.code, 'ENOSPC');
          assert.match(stderr.text(), /self-heal failed/);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_noop_on_unsupported_platform():
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-unsup-');
          const stderr = captureStderr();
          const result = await launcher.ensureSidecarsFresh({
            packageRoot: fx.root,
            installRoot: fx.installRoot,
            platform: 'freebsd',
            arch: 'x64',
            stderr: stderr.stream,
            env: { CODEXPP_LANG: 'en' },
          });
          assert.equal(result.action, 'noop');
          assert.equal(result.drift, 'unsupported');
          assert.equal(stderr.text(), '');
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


def test_self_heal_does_not_run_for_doctor():
    # Doctor must remain a read-only inspector even when drift=mismatch.
    assert_node_ok(
        SELF_HEAL_FIXTURE
        + r"""
        (async () => {
          const fx = makeFixture('cxpp-heal-doctor-');
          fs.mkdirSync(fx.installRoot, { recursive: true });
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'silent-old');
          fs.writeFileSync(path.join(fx.installRoot, 'codex-plus-plus-manager.exe'), 'manager-old');
          fs.writeFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), '1.2.5\n');
          const sidecarMtimeBefore = fs.statSync(path.join(fx.installRoot, 'codex-plus-plus.exe')).mtimeMs;

          // Capture stdout (doctor prints its report on stdout, not stderr).
          const originalLog = console.log;
          const lines = [];
          console.log = (msg) => { lines.push(String(msg)); };
          try {
            const result = await launcher.runLauncher(['doctor'], {
              packageRoot: fx.root,
              installRoot: fx.installRoot,
              platform: 'win32',
              arch: 'x64',
              env: { CODEXPP_LANG: 'en' },
            });
            assert.equal(result.status, 0);
          } finally {
            console.log = originalLog;
          }
          // Sidecar bytes must not have changed; stamp must still report 1.2.5.
          assert.equal(fs.readFileSync(path.join(fx.installRoot, 'codex-plus-plus.exe'), 'utf8'), 'silent-old');
          assert.equal(fs.readFileSync(path.join(fx.installRoot, launcher.SIDECAR_VERSION_STAMP), 'utf8').trim(), '1.2.5');
          assert.equal(fs.statSync(path.join(fx.installRoot, 'codex-plus-plus.exe')).mtimeMs, sidecarMtimeBefore);
        })().catch((error) => { console.error(error); process.exit(1); });
        """
    )


