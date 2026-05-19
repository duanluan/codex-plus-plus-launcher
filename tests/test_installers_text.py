from __future__ import annotations

from pathlib import Path


def test_install_sh_mentions_force_reinstall_fallback():
    content = Path("install.sh").read_text(encoding="utf-8")

    assert "should_force_reinstall" in content
    assert "--ignore-installed --no-deps" in content
    assert "pip install" in content
    assert "--user" not in content


def test_npm_package_postinstall_is_explicitly_scoped():
    content = Path("package.json").read_text(encoding="utf-8")

    assert '"build:binary-local": "node npm/build-local-binary.cjs"' in content
    assert '"prepack": "node npm/verify-package.cjs"' in content
    assert '"postinstall": "node install-npm.cjs"' in content
    assert '"smoke:npm-local": "node npm/smoke-install.cjs"' in content
    assert "install-npm.cjs" in content
    assert "npm/install.js" in content
    assert "npm/build-local-binary.cjs" in content
    assert "npm/verify-package.cjs" in content
    assert "npm/smoke-install.cjs" in content
    assert '"cpxx"' not in content
    assert "pip install" not in content
    assert "--user" not in content
    assert "PYTHONUSERBASE" not in content


def test_npm_postinstall_uses_npm_specific_command():
    content = Path("npm/install.js").read_text(encoding="utf-8")

    assert "npm-postinstall" in content
    assert "'setup'" not in content
    assert "installGlobalBinary" in content
    assert "CODEXPP_NO_AUTO_INJECT" not in content
    assert "CODEXPP_SHORTCUT_MODE" not in content


def test_npm_launcher_defaults_to_bundled_binary():
    launcher = Path("npm/launcher.js").read_text(encoding="utf-8")
    cxpp = Path("npm/cxpp.js").read_text(encoding="utf-8")

    assert "bin" in launcher
    assert "platformBinaryName" in launcher
    assert "installGlobalBinary" in launcher
    assert "cxpp-native-" in launcher
    assert "preferredBinaryPath" in launcher
    assert "globalBinaryPath" in launcher
    assert "CODEXPP_ALLOW_PYTHON_FALLBACK" in launcher
    assert "CODEXPP_PYTHON" in launcher
    assert "readdirSync" in launcher
    assert "CODEXPP_LOCKED_OLD_BINARY" in launcher
    assert "findRunningProcessesForPath" in launcher
    assert "runLauncher" in cxpp
    assert "codex_plus_plus_launcher" not in cxpp


def test_prepack_verifier_checks_platform_binary():
    content = Path("npm/verify-package.cjs").read_text(encoding="utf-8")

    assert "bin" in content
    assert "cxpp-" in content
    assert "missing required bundled binary" in content
    assert "missing required bundled icon asset" in content


def test_local_binary_builder_uses_pyinstaller_and_upstream_bundle():
    content = Path("npm/build-local-binary.cjs").read_text(encoding="utf-8")

    assert "PyInstaller" in content
    assert "write_latest_release_json" in content
    assert "install_spec" in content
    assert "--add-data" in content
    assert "upstream-release.json" in content
    assert "codex-plus-plus.ico" in content
    assert "codex_plus_plus_launcher" in content
    assert "built local binary" in content


def test_smoke_install_skips_real_shortcuts():
    content = Path("npm/smoke-install.cjs").read_text(encoding="utf-8")

    assert "CODEXPP_SHORTCUT_MODE: 'skip'" in content


def test_smoke_install_uses_current_package_version_tarball():
    content = Path("npm/smoke-install.cjs").read_text(encoding="utf-8")

    assert "require(path.join(root, 'package.json'))" in content
    assert "name.slice(1).replace('/', '-')" in content
    assert "`${tarballName}-${version}.tgz`" in content
    assert ".sort()" not in content


def test_package_exposes_only_explicit_commands():
    content = Path("package.json").read_text(encoding="utf-8")

    assert '"version": "0.1.10"' in content
    assert '"codex_plus_plus_launcher/*.py"' in content
    assert '"codex_plus_plus_launcher/assets/*"' in content
    assert '"bin/*"' in content
    assert '"cxpp": "npm/cxpp.js"' in content
    assert '"codexpp": "npm/cxpp.js"' in content


def test_readme_explains_wrapper_owns_upstream_updates():
    content = Path("README.md").read_text(encoding="utf-8")
    content_en = Path("README_EN.md").read_text(encoding="utf-8")

    assert "更新这个 wrapper 包" in content
    assert "上游 GitHub Release" in content
    assert "updating this wrapper package" in content_en
    assert "latest upstream GitHub Release" in content_en
