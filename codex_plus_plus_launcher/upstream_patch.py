from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VM_DEFAULTS_SOURCE = (
    "return { pluginEntryUnlock: true, forcePluginInstall: true, sessionDelete: true, "
    "markdownExport: true, projectMove: true, conversationTimeline: true, nativeMenuPlacement: true };"
)
VM_DEFAULTS_TARGET = (
    "return { pluginEntryUnlock: true, forcePluginInstall: true, sessionDelete: true, "
    "markdownExport: true, projectMove: false, conversationTimeline: false, nativeMenuPlacement: true };"
)


@dataclass(frozen=True)
class PatchResult:
    status: str
    path: Path | None = None


def patch_renderer_defaults(text: str) -> tuple[str, bool]:
    if VM_DEFAULTS_TARGET in text:
        return text, False
    if VM_DEFAULTS_SOURCE not in text:
        return text, False
    return text.replace(VM_DEFAULTS_SOURCE, VM_DEFAULTS_TARGET, 1), True


def detect_vm_patch(text: str) -> bool:
    return VM_DEFAULTS_TARGET in text


def apply_vm_patch(renderer_script_path: Path) -> PatchResult:
    if not renderer_script_path.exists():
        return PatchResult("missing", renderer_script_path)
    original = renderer_script_path.read_text(encoding="utf-8")
    updated, changed = patch_renderer_defaults(original)
    if not changed:
        return PatchResult("already_patched" if detect_vm_patch(original) else "unchanged", renderer_script_path)
    renderer_script_path.write_text(updated, encoding="utf-8")
    return PatchResult("patched", renderer_script_path)
