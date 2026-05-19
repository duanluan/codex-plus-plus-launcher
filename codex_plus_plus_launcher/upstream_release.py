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
UPSTREAM_RELEASE_LATEST_URL = f"https://github.com/{UPSTREAM_REPOSITORY}/releases/latest"
UPSTREAM_USER_AGENT = "codex-plus-plus-launcher"


@dataclass(frozen=True)
class UpstreamRelease:
    version: str
    html_url: str
    asset_name: str | None = None
    asset_url: str | None = None
    source_zip_url: str | None = None


def _select_release_asset(assets: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    named_assets = [asset for asset in assets if asset.get("name") and asset.get("browser_download_url")]
    for asset in named_assets:
        name = str(asset["name"])
        url = str(asset["browser_download_url"])
        if name.endswith(".whl"):
            return name, url
    for asset in named_assets:
        name = str(asset["name"])
        url = str(asset["browser_download_url"])
        if name.lower().endswith((".zip", ".tar.gz", ".tgz")):
            return name, url
    return None, None


def parse_latest_release_payload(payload: dict[str, Any]) -> UpstreamRelease:
    tag_name = str(payload["tag_name"])
    asset_name, asset_url = _select_release_asset(payload.get("assets", []))
    return UpstreamRelease(
        version=tag_name,
        html_url=str(payload.get("html_url") or ""),
        asset_name=asset_name,
        asset_url=asset_url,
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


def fetch_latest_release(timeout: int = 20) -> UpstreamRelease:
    request = urllib.request.Request(
        UPSTREAM_RELEASE_API_URL,
        headers=_github_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        return parse_latest_release_payload(payload)
    except urllib.error.HTTPError as error:
        if error.code not in {403, 429}:
            raise
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
        "source_zip_url": release.source_zip_url,
        "install_spec": latest_release_install_spec(release),
    }
    Path(output_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
