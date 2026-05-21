from __future__ import annotations

from pathlib import Path


def test_readme_uses_registry_install_commands():
    content = Path("README.md").read_text(encoding="utf-8")

    assert "npm install -g @duanluan/codex-plus-plus-launcher" in content
    assert "python -m pip install codex-plus-plus-launcher" not in content


def test_release_workflow_publishes_npm_only():
    content = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "build-sidecars" in content
    assert "windows-latest" in content
    assert "macos-14" in content
    assert "macos-15-intel" in content
    assert "ubuntu-latest" in content
    assert "linux-x64" in content
    assert "write_latest_release_json" in content
    assert "BigPizzaV3/CodexPlusPlus.git" in content
    assert "upstream/apps/codex-plus-manager" in content
    assert "npm install --package-lock=false" in content
    assert "npm run vite:build" in content
    assert "cargo build --release" in content
    assert "-p codex-plus-launcher" in content
    assert "codex-plus-plus-manager" in content
    assert "if: matrix.rust-targets == ''" in content
    assert "if: matrix.rust-targets != ''" in content
    assert 'shell: bash\n        run: git clone --depth 1 --branch "${CODEXPP_UPSTREAM_REF}"' in content
    assert "actions/download-artifact@v4" in content
    assert "path: upstream-bin" in content
    assert "npm publish --access public" in content
    assert "secrets.NPM_TOKEN" in content
    assert 'tags:\n      - "v*"' in content
    assert "python - <<'PY'" in content
    assert "CODEXPP_UPSTREAM_COMMIT" in content


def test_manual_npm_publish_workflow_exists():
    content = Path(".github/workflows/publish-npm-bootstrap.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch" in content
    assert "build-sidecars" in content
    assert "ubuntu-latest" in content
    assert "linux-x64" in content
    assert "write_latest_release_json" in content
    assert "BigPizzaV3/CodexPlusPlus.git" in content
    assert "upstream/apps/codex-plus-manager" in content
    assert "cargo build --release" in content
    assert "-p codex-plus-launcher" in content
    assert "codex-plus-plus-manager" in content
    assert "if: matrix.rust-targets == ''" in content
    assert "if: matrix.rust-targets != ''" in content
    assert 'shell: bash\n        run: git clone --depth 1 --branch "${CODEXPP_UPSTREAM_REF}"' in content
    assert "actions/download-artifact@v4" in content
    assert "npm whoami" in content
    assert "npm publish --access public" in content
    assert "secrets.NPM_TOKEN" in content
    assert "path: upstream-bin" in content


def test_sync_upstream_workflow_exists():
    content = Path(".github/workflows/sync-upstream-wrapper.yml").read_text(encoding="utf-8")

    assert "schedule:" in content
    assert "workflow_dispatch:" in content
    assert "write_latest_release_json" in content
    assert ".github/upstream-sync/latest.json" in content
    assert "gh pr create" in content


def test_legacy_npm_workflow_retires_pre_0_1_10_versions():
    content = Path(".github/workflows/deprecate-legacy-npm.yml").read_text(encoding="utf-8")

    assert "Retire pre-0.1.10 versions" in content
    assert "npm unpublish" in content
    assert "--force" in content
    assert "npm deprecate" in content
    assert "0.1.7" in content
    assert "0.1.8" in content
    assert "0.1.9" in content
    assert "Please upgrade to 0.1.10 or later" in content
