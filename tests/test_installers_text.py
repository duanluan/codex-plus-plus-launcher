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

    assert '"build:sidecars-local": "node npm/build-local-binary.cjs"' in content
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
    assert "runLauncher" in content
    assert "CODEXPP_NO_AUTO_INJECT" not in content


def test_npm_launcher_dispatches_to_bundled_sidecars():
    launcher = Path("npm/launcher.js").read_text(encoding="utf-8")
    cxpp = Path("npm/cxpp.js").read_text(encoding="utf-8")

    assert "upstream-bin" in launcher
    assert "codex-plus-plus-manager" in launcher
    assert "SUPPORTED_PLATFORMS" in launcher
    assert "installSidecars" in launcher
    assert "installMacEntrypoints" in launcher
    assert "installWindowsEntrypoints" in launcher
    assert "spawnSidecar" in launcher
    assert "install_mode=sidecar" in launcher
    assert "install_mode=unsupported" in launcher
    assert "CODEXPP_LOCKED_OLD_BINARY" in launcher
    assert "findRunningProcessesForPath" in launcher
    assert "runLauncher" in cxpp
    assert "codex_plus_plus_launcher" not in cxpp


def test_prepack_verifier_checks_sidecars():
    content = Path("npm/verify-package.cjs").read_text(encoding="utf-8")

    assert "upstream-bin" in content
    assert "codex-plus-plus-manager" in content
    assert "win32-x64" in content
    assert "darwin-x64" in content
    assert "darwin-arm64" in content
    assert "missing required bundled upstream sidecar" in content
    assert "missing required bundled icon asset" in content


def test_local_sidecar_builder_uses_upstream_rust_workspace():
    content = Path("npm/build-local-binary.cjs").read_text(encoding="utf-8")

    assert "BigPizzaV3/CodexPlusPlus.git" in content
    assert "CODEXPP_UPSTREAM_REF" in content
    assert "defaultUpstreamRef" in content
    assert "CODEXPP_SIDECAR_PLATFORM" in content
    assert "'install'" in content
    assert "vite:build" in content
    assert "cargo" in content
    assert "build" in content
    assert "codex-plus-plus-manager" in content
    assert "upstream-release.json" in content
    assert "codex-plus-plus.ico" in content
    assert "codex-plus-plus.png" in content
    assert "applyPluginUnlockPatch" in content
    assert "codex-plus-plus-plugin-unlock.patch" in content
    assert "built upstream sidecars" in content


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

    assert '"version": "1.2.16"' in content
    assert '"codex_plus_plus_launcher/*.py"' in content
    assert '"codex_plus_plus_launcher/assets/*"' in content
    assert '"upstream-bin/**"' in content
    assert '"patches/**"' in content
    assert '"npm/plugin-auth-unlocked.js"' in content
    assert '"cxpp": "npm/cxpp.js"' in content
    assert '"codexpp": "npm/cxpp.js"' in content


def test_npm_includes_aur_plugin_unlock_fix():
    patch = Path("patches/codex-plus-plus-plugin-unlock.patch").read_text(encoding="utf-8")
    auth = Path("npm/plugin-auth-unlocked.js").read_text(encoding="utf-8")
    launcher = Path("npm/launcher.js").read_text(encoding="utf-8")

    assert "codexPluginNavUnlockVersion" in patch
    assert "unlockPluginNavButtons" in patch
    assert "pluginMarketplaceUnlock" in patch
    assert "function e(e){return false}export{e as t};" in auth
    assert "pluginAuthUnlockPath" in launcher
    assert "writeLinuxCodexShim" in launcher
    assert "plugin-auth-*.js" in launcher


def test_readme_explains_wrapper_owns_upstream_updates():
    content = Path("README.md").read_text(encoding="utf-8")
    content_en = Path("README_EN.md").read_text(encoding="utf-8")

    assert "更新这个 wrapper 包" in content
    assert "上游 GitHub Release" in content
    assert "Codex++ 管理工具" in content
    assert "codex-desktop-linux" in content
    assert "codex.exe" in content
    assert "Linux 暂不内置 Codex++ 管理工具" in content
    assert "updating this wrapper package" in content_en
    assert "latest upstream GitHub Release" in content_en
    assert "Codex++ Manager" in content_en
    assert "codex-desktop-linux" in content_en
    assert "codex.exe" in content_en
    assert "Codex++ Manager is not bundled on Linux yet" in content_en
