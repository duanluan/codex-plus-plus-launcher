from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UPSTREAM_REPOSITORY = "BigPizzaV3/CodexPlusPlus"
UPSTREAM_RELEASE_API_URL = f"https://api.github.com/repos/{UPSTREAM_REPOSITORY}/releases/latest"
UPSTREAM_TAGS_API_URL = f"https://api.github.com/repos/{UPSTREAM_REPOSITORY}/tags"
UPSTREAM_RELEASE_LATEST_URL = f"https://github.com/{UPSTREAM_REPOSITORY}/releases/latest"
UPSTREAM_USER_AGENT = "codex-plus-plus-launcher"


@dataclass(frozen=True)
class UpstreamRelease:
    version: str
    html_url: str
    asset_name: str | None = None
    asset_url: str | None = None
    windows_asset_name: str | None = None
    windows_asset_url: str | None = None
    macos_x64_asset_name: str | None = None
    macos_x64_asset_url: str | None = None
    macos_arm64_asset_name: str | None = None
    macos_arm64_asset_url: str | None = None
    source_zip_url: str | None = None
    commit: str | None = None
    repository: str = UPSTREAM_REPOSITORY


def _asset_pairs(assets: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (str(asset["name"]), str(asset["browser_download_url"]))
        for asset in assets
        if asset.get("name") and asset.get("browser_download_url")
    ]


def _select_named_asset(assets: list[tuple[str, str]], *needles: str, suffix: str | tuple[str, ...]) -> tuple[str | None, str | None]:
    suffixes = (suffix,) if isinstance(suffix, str) else suffix
    for name, url in assets:
        lowered = name.lower()
        if all(needle in lowered for needle in needles) and lowered.endswith(suffixes):
            return name, url
    return None, None


def _select_release_asset(assets: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    named_assets = _asset_pairs(assets)
    for name, url in named_assets:
        if name.lower().endswith((".whl", "-setup.exe", "_setup.exe", "setup.exe", ".dmg")):
            return name, url
    for name, url in named_assets:
        if name.lower().endswith((".zip", ".tar.gz", ".tgz")):
            return name, url
    return None, None


def _tag_sort_key(tag_name: str) -> tuple[int, ...]:
    value = tag_name.strip().lstrip("vV")
    parts: list[int] = []
    for part in value.split("."):
        if not part.isdigit():
            break
        parts.append(int(part))
    return tuple(parts)


def _latest_stable_tag_from_payload(payload: list[dict[str, Any]]) -> UpstreamRelease:
    tags = [
        item
        for item in payload
        if isinstance(item.get("name"), str) and _tag_sort_key(str(item["name"]))
    ]
    if not tags:
        raise RuntimeError("failed to resolve upstream latest tag")
    selected = max(tags, key=lambda item: _tag_sort_key(str(item["name"])))
    tag_name = str(selected["name"])
    commit = selected.get("commit") if isinstance(selected.get("commit"), dict) else {}
    commit_sha = commit.get("sha") if isinstance(commit.get("sha"), str) else None
    return UpstreamRelease(
        version=tag_name,
        html_url=f"https://github.com/{UPSTREAM_REPOSITORY}/releases/tag/{tag_name}",
        source_zip_url=f"https://github.com/{UPSTREAM_REPOSITORY}/archive/refs/tags/{tag_name}.zip",
        commit=commit_sha,
    )


def parse_latest_release_payload(payload: dict[str, Any]) -> UpstreamRelease:
    tag_name = str(payload["tag_name"])
    assets_payload = payload.get("assets", [])
    assets = _asset_pairs(assets_payload)
    asset_name, asset_url = _select_release_asset(assets_payload)
    windows_asset_name, windows_asset_url = _select_named_asset(assets, "windows", "x64", suffix=".exe")
    macos_x64_asset_name, macos_x64_asset_url = _select_named_asset(assets, "macos", "x64", suffix=".dmg")
    macos_arm64_asset_name, macos_arm64_asset_url = _select_named_asset(assets, "macos", "arm64", suffix=".dmg")
    return UpstreamRelease(
        version=tag_name,
        html_url=str(payload.get("html_url") or ""),
        asset_name=asset_name,
        asset_url=asset_url,
        windows_asset_name=windows_asset_name,
        windows_asset_url=windows_asset_url,
        macos_x64_asset_name=macos_x64_asset_name,
        macos_x64_asset_url=macos_x64_asset_url,
        macos_arm64_asset_name=macos_arm64_asset_name,
        macos_arm64_asset_url=macos_arm64_asset_url,
        source_zip_url=f"https://github.com/{UPSTREAM_REPOSITORY}/archive/refs/tags/{tag_name}.zip",
    )


def _github_headers() -> dict[str, str]:
    headers = {"User-Agent": UPSTREAM_USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _latest_release_from_redirect(timeout: int) -> UpstreamRelease:
    request = urllib.request.Request(UPSTREAM_RELEASE_LATEST_URL, headers={"User-Agent": UPSTREAM_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
    tag_name = final_url.rstrip("/").rsplit("/", 1)[-1]
    if not tag_name or tag_name == "latest":
        raise RuntimeError("failed to resolve upstream latest release tag")
    return UpstreamRelease(
        version=tag_name,
        html_url=f"https://github.com/{UPSTREAM_REPOSITORY}/releases/tag/{tag_name}",
        source_zip_url=f"https://github.com/{UPSTREAM_REPOSITORY}/archive/refs/tags/{tag_name}.zip",
    )


def _latest_release_from_tags_api(timeout: int) -> UpstreamRelease:
    request = urllib.request.Request(
        UPSTREAM_TAGS_API_URL,
        headers=_github_headers(),
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return _latest_stable_tag_from_payload(payload)


def _with_newer_tag_release(release: UpstreamRelease, timeout: int) -> UpstreamRelease:
    try:
        tag_release = _latest_release_from_tags_api(timeout)
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError):
        return release
    if _tag_sort_key(tag_release.version) > _tag_sort_key(release.version):
        return tag_release
    return release


def fetch_latest_release(timeout: int = 20) -> UpstreamRelease:
    request = urllib.request.Request(
        UPSTREAM_RELEASE_API_URL,
        headers=_github_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        return _with_newer_tag_release(parse_latest_release_payload(payload), timeout)
    except urllib.error.HTTPError as error:
        if error.code not in {403, 429}:
            raise
        try:
            return _latest_release_from_tags_api(timeout)
        except urllib.error.HTTPError as tag_error:
            if tag_error.code not in {403, 429}:
                raise
            return _latest_release_from_redirect(timeout)
        except urllib.error.URLError:
            return _latest_release_from_redirect(timeout)
    except urllib.error.URLError:
        try:
            return _latest_release_from_tags_api(timeout)
        except urllib.error.URLError:
            return _latest_release_from_redirect(timeout)


def latest_release_install_spec(release: UpstreamRelease) -> str:
    return release.asset_url or release.source_zip_url or ""


def write_latest_release_json(output_path: str | Path) -> None:
    release = fetch_latest_release()
    payload = {
        "version": release.version,
        "html_url": release.html_url,
        "asset_name": release.asset_name,
        "asset_url": release.asset_url,
        "windows_asset_name": release.windows_asset_name,
        "windows_asset_url": release.windows_asset_url,
        "macos_x64_asset_name": release.macos_x64_asset_name,
        "macos_x64_asset_url": release.macos_x64_asset_url,
        "macos_arm64_asset_name": release.macos_arm64_asset_name,
        "macos_arm64_asset_url": release.macos_arm64_asset_url,
        "source_zip_url": release.source_zip_url,
        "install_spec": latest_release_install_spec(release),
        "commit": release.commit,
        "repository": release.repository,
    }
    Path(output_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
