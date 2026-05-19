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


def test_locked_stale_binary_yes_terminates_and_retries():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');
        const locked = 'C:\\prefix\\cxpp-native-0.1.7-win32-x64.exe';
        let attempts = 0;
        let terminated = null;
        const fakeFs = {
          rmSync(candidate) {
            assert.equal(candidate, locked);
            attempts += 1;
            if (attempts === 1) {
              const error = new Error('locked');
              error.code = 'EPERM';
              throw error;
            }
          },
        };

        (async () => {
          await launcher.removeStaleGlobalBinary(locked, 'C:\\prefix\\cxpp-native-0.1.10-win32-x64.exe', {
            fs: fakeFs,
            platform: 'win32',
            stdin: { isTTY: true },
            stdout: { isTTY: true },
            findRunningProcessesForPath: () => [{ ProcessId: 123, ExecutablePath: locked }],
            promptYesNo: async () => true,
            terminateProcesses: (processes) => { terminated = processes.map((processInfo) => processInfo.ProcessId); },
          });

          assert.equal(attempts, 2);
          assert.deepEqual(terminated, [123]);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_locked_stale_binary_no_fails_with_friendly_error():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');
        const locked = 'C:\\prefix\\cxpp-native-0.1.7-win32-x64.exe';
        let prompted = false;
        let terminated = false;
        const fakeFs = {
          rmSync() {
            const error = new Error('locked');
            error.code = 'EPERM';
            throw error;
          },
        };

        (async () => {
          await assert.rejects(
            launcher.removeStaleGlobalBinary(locked, 'C:\\prefix\\cxpp-native-0.1.10-win32-x64.exe', {
              fs: fakeFs,
              platform: 'win32',
              stdin: { isTTY: true },
              stdout: { isTTY: true },
              findRunningProcessesForPath: () => [{ ProcessId: 123, ExecutablePath: locked }],
              promptYesNo: async () => { prompted = true; return false; },
              terminateProcesses: () => { terminated = true; },
            }),
            (error) => {
              assert.equal(error.code, 'CODEXPP_LOCKED_OLD_BINARY');
              assert.match(error.message, /Close Codex\+\+ \/ Codex App|关闭 Codex\+\+ \/ Codex App/);
              return true;
            },
          );
          assert.equal(prompted, true);
          assert.equal(terminated, false);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_locked_stale_binary_noninteractive_does_not_prompt():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');
        const locked = 'C:\\prefix\\cxpp-native-0.1.7-win32-x64.exe';
        let prompted = false;
        const fakeFs = {
          rmSync() {
            const error = new Error('locked');
            error.code = 'EPERM';
            throw error;
          },
        };

        (async () => {
          await assert.rejects(
            launcher.removeStaleGlobalBinary(locked, 'C:\\prefix\\cxpp-native-0.1.10-win32-x64.exe', {
              fs: fakeFs,
              platform: 'win32',
              stdin: { isTTY: false },
              stdout: { isTTY: false },
              env: { CI: 'true' },
              findRunningProcessesForPath: () => [{ ProcessId: 123, ExecutablePath: locked }],
              promptYesNo: async () => { prompted = true; return true; },
              promptYesNoWindowsPopup: async () => { prompted = true; return true; },
            }),
            { code: 'CODEXPP_LOCKED_OLD_BINARY' },
          );
          assert.equal(prompted, false);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_locked_stale_binary_npm_windows_popup_yes_terminates_and_retries():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');
        const locked = 'C:\\prefix\\cxpp-native-0.1.7-win32-x64.exe';
        let attempts = 0;
        let terminalPrompted = false;
        let popupPrompted = false;
        let terminated = null;
        const fakeFs = {
          rmSync(candidate) {
            assert.equal(candidate, locked);
            attempts += 1;
            if (attempts === 1) {
              const error = new Error('locked');
              error.code = 'EPERM';
              throw error;
            }
          },
        };

        (async () => {
          await launcher.removeStaleGlobalBinary(locked, 'C:\\prefix\\cxpp-native-0.1.10-win32-x64.exe', {
            fs: fakeFs,
            platform: 'win32',
            stdin: { isTTY: false },
            stdout: { isTTY: false },
            env: {},
            findRunningProcessesForPath: () => [{ ProcessId: 123, ExecutablePath: locked }],
            promptYesNo: async () => { terminalPrompted = true; return true; },
            promptYesNoWindowsPopup: async (question) => {
              assert.match(question, /Codex\+\+|旧版/);
              assert.match(question, /cxpp-native-0\.1\.7-win32-x64\.exe/);
              popupPrompted = true;
              return true;
            },
            terminateProcesses: (processes) => { terminated = processes.map((processInfo) => processInfo.ProcessId); },
          });

          assert.equal(attempts, 2);
          assert.equal(terminalPrompted, false);
          assert.equal(popupPrompted, true);
          assert.deepEqual(terminated, [123]);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_locked_stale_binary_ci_does_not_show_windows_popup():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const launcher = require('./npm/launcher.js');
        const locked = 'C:\\prefix\\cxpp-native-0.1.7-win32-x64.exe';
        let popupPrompted = false;
        const fakeFs = {
          rmSync() {
            const error = new Error('locked');
            error.code = 'EPERM';
            throw error;
          },
        };

        (async () => {
          await assert.rejects(
            launcher.removeStaleGlobalBinary(locked, 'C:\\prefix\\cxpp-native-0.1.10-win32-x64.exe', {
              fs: fakeFs,
              platform: 'win32',
              stdin: { isTTY: false },
              stdout: { isTTY: false },
              env: { CI: 'true' },
              findRunningProcessesForPath: () => [{ ProcessId: 123, ExecutablePath: locked }],
              promptYesNoWindowsPopup: async () => { popupPrompted = true; return true; },
            }),
            { code: 'CODEXPP_LOCKED_OLD_BINARY' },
          );
          assert.equal(popupPrompted, false);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )


def test_install_global_binary_removes_old_binary_and_preserves_current():
    assert_node_ok(
        r"""
        const assert = require('node:assert/strict');
        const path = require('node:path');
        const launcher = require('./npm/launcher.js');
        const prefix = 'C:\\prefix';
        const source = 'C:\\pkg\\bin\\cxpp-win32-x64.exe';
        const current = path.join(prefix, 'cxpp-native-0.1.10-win32-x64.exe');
        const old = path.join(prefix, 'cxpp-native-0.1.8-win32-x64.exe');
        const files = new Set([source.toLowerCase()]);
        const removed = [];
        const fakeFs = {
          existsSync(candidate) {
            return files.has(String(candidate).toLowerCase());
          },
          mkdirSync() {},
          copyFileSync(src, dest) {
            assert.equal(src, source);
            assert.equal(dest, current);
            files.add(dest.toLowerCase());
          },
          chmodSync(candidate) {
            assert.equal(candidate, current);
          },
          readdirSync() {
            return [
              { name: path.basename(current), isFile: () => true },
              { name: path.basename(old), isFile: () => true },
            ];
          },
          rmSync(candidate) {
            removed.push(candidate);
          },
        };

        (async () => {
          const installed = await launcher.installGlobalBinary({
            fs: fakeFs,
            platform: 'win32',
            arch: 'x64',
            packageVersion: '0.1.10',
            globalPrefix: prefix,
            bundledBinaryPath: source,
          });

          assert.equal(installed, current);
          assert.deepEqual(removed, [old]);
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )
