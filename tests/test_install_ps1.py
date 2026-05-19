from __future__ import annotations

from pathlib import Path


def test_install_ps1_uses_exit_code_check():
    content = Path("install.ps1").read_text(encoding="utf-8")

    assert "$ErrorActionPreference = 'Continue'" in content
    assert "$status = $LASTEXITCODE" in content
    assert "if ($status -eq 0)" in content
    assert "Test-ShouldForceReinstall" in content
    assert "--ignore-installed" in content
    assert "Get-UvBinDirectory" in content
    assert "[switch]$UseUv" in content
    assert "uv install is opt-in. Re-run with -UseUv." in content
    assert "Test-PythonEnvironmentWritable" in content
    assert "pip_requires_writable_env" in content
    assert "Remove-BrokenWindowsNpmShims" in content
