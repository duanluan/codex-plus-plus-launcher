from __future__ import annotations

from codex_plus_plus_launcher.upstream_patch import VM_DEFAULTS_SOURCE, VM_DEFAULTS_TARGET, detect_vm_patch, patch_renderer_defaults


def test_patch_renderer_defaults_disables_heavy_features():
    updated, changed = patch_renderer_defaults(VM_DEFAULTS_SOURCE)

    assert changed is True
    assert updated == VM_DEFAULTS_TARGET
    assert detect_vm_patch(updated) is True
