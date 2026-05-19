from __future__ import annotations

from pathlib import Path


def test_readme_uses_registry_install_commands():
    content = Path("README.md").read_text(encoding="utf-8")

    assert "npm install -g @duanluan/codex-plus-plus-launcher" in content
    assert "python -m pip install codex-plus-plus-launcher" not in content


def test_release_workflow_publishes_npm_only():
    content = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "pyinstaller --onefile" in content
    assert "--collect-all codex_session_delete" in content
    assert '--add-data "codex_plus_plus_launcher/assets/codex-plus-plus.ico:codex_plus_plus_launcher/assets"' in content
    assert '--add-data ".github/upstream-release.json:codex_plus_plus_launcher"' in content
    assert "write_latest_release_json" in content
    assert "install_spec" in content
    assert "codex_plus_plus_launcher/__main__.py" in content
    assert "actions/download-artifact@v4" in content
    assert "path: bin" in content
    assert "npm publish --access public" in content
    assert "secrets.NPM_TOKEN" in content
    assert 'tags:\n      - "v*"' in content


def test_manual_npm_publish_workflow_exists():
    content = Path(".github/workflows/publish-npm-bootstrap.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch" in content
    assert "pyinstaller --onefile" in content
    assert "--collect-all codex_session_delete" in content
    assert '--add-data "codex_plus_plus_launcher/assets/codex-plus-plus.ico:codex_plus_plus_launcher/assets"' in content
    assert '--add-data ".github/upstream-release.json:codex_plus_plus_launcher"' in content
    assert "write_latest_release_json" in content
    assert "install_spec" in content
    assert "actions/download-artifact@v4" in content
    assert "npm whoami" in content
    assert "npm publish --access public" in content
    assert "secrets.NPM_TOKEN" in content


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
