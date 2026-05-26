from __future__ import annotations

import urllib.error

from codex_plus_plus_launcher import upstream_release


def test_github_headers_uses_available_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

    headers = upstream_release._github_headers()

    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["User-Agent"] == "codex-plus-plus-launcher"


def test_fetch_latest_release_falls_back_to_redirect_on_rate_limit(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url in {upstream_release.UPSTREAM_RELEASE_API_URL, upstream_release.UPSTREAM_TAGS_API_URL}:
            raise urllib.error.HTTPError(request.full_url, 403, "rate limit exceeded", hdrs=None, fp=None)
        return type(
            "Response",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: None,
                "geturl": lambda self: f"https://github.com/{upstream_release.UPSTREAM_REPOSITORY}/releases/tag/v1.2.3",
            },
        )()

    monkeypatch.setattr(upstream_release.urllib.request, "urlopen", fake_urlopen)

    release = upstream_release.fetch_latest_release()

    assert calls == [
        upstream_release.UPSTREAM_RELEASE_API_URL,
        upstream_release.UPSTREAM_TAGS_API_URL,
        upstream_release.UPSTREAM_RELEASE_LATEST_URL,
    ]
    assert release.version == "v1.2.3"
    assert release.asset_url is None
    assert release.source_zip_url == f"https://github.com/{upstream_release.UPSTREAM_REPOSITORY}/archive/refs/tags/v1.2.3.zip"


def test_parse_latest_release_payload_selects_platform_assets():
    payload = {
        "tag_name": "v1.1.7",
        "html_url": "https://github.com/BigPizzaV3/CodexPlusPlus/releases/tag/v1.1.7",
        "assets": [
            {
                "name": "CodexPlusPlus-1.1.7-windows-x64-setup.exe",
                "browser_download_url": "https://example.test/windows.exe",
            },
            {
                "name": "CodexPlusPlus-1.1.7-macos-x64.dmg",
                "browser_download_url": "https://example.test/macos-x64.dmg",
            },
            {
                "name": "CodexPlusPlus-1.1.7-macos-arm64.dmg",
                "browser_download_url": "https://example.test/macos-arm64.dmg",
            },
            {
                "name": "Source code (zip)",
                "browser_download_url": "https://example.test/source.zip",
            },
        ],
    }

    release = upstream_release.parse_latest_release_payload(payload)

    assert release.version == "v1.1.7"
    assert release.asset_name == "CodexPlusPlus-1.1.7-windows-x64-setup.exe"
    assert release.asset_url == "https://example.test/windows.exe"
    assert release.windows_asset_name == "CodexPlusPlus-1.1.7-windows-x64-setup.exe"
    assert release.windows_asset_url == "https://example.test/windows.exe"
    assert release.macos_x64_asset_name == "CodexPlusPlus-1.1.7-macos-x64.dmg"
    assert release.macos_arm64_asset_name == "CodexPlusPlus-1.1.7-macos-arm64.dmg"
    assert release.source_zip_url == f"https://github.com/{upstream_release.UPSTREAM_REPOSITORY}/archive/refs/tags/v1.1.7.zip"


def test_fetch_latest_release_falls_back_to_highest_stable_tag_on_rate_limit(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url == upstream_release.UPSTREAM_RELEASE_API_URL:
            raise urllib.error.HTTPError(request.full_url, 403, "rate limit exceeded", hdrs=None, fp=None)
        assert request.full_url == upstream_release.UPSTREAM_TAGS_API_URL
        payload = b"""
        [
          {"name": "v1.1.0", "commit": {"sha": "old"}},
          {"name": "v1.1.7", "commit": {"sha": "333c2b0c"}},
          {"name": "v1.1.2", "commit": {"sha": "older"}}
        ]
        """
        return type(
            "Response",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: None,
                "read": lambda self: payload,
            },
        )()

    monkeypatch.setattr(upstream_release.urllib.request, "urlopen", fake_urlopen)

    release = upstream_release.fetch_latest_release()

    assert calls == [upstream_release.UPSTREAM_RELEASE_API_URL, upstream_release.UPSTREAM_TAGS_API_URL]
    assert release.version == "v1.1.7"
    assert release.commit == "333c2b0c"


def test_fetch_latest_release_falls_back_to_tags_on_url_error(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url == upstream_release.UPSTREAM_RELEASE_API_URL:
            raise urllib.error.URLError("network reset")
        assert request.full_url == upstream_release.UPSTREAM_TAGS_API_URL
        payload = b"""
        [
          {"name": "v1.1.7", "commit": {"sha": "333c2b0c"}},
          {"name": "v1.1.6", "commit": {"sha": "older"}}
        ]
        """
        return type(
            "Response",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: None,
                "read": lambda self: payload,
            },
        )()

    monkeypatch.setattr(upstream_release.urllib.request, "urlopen", fake_urlopen)

    release = upstream_release.fetch_latest_release()

    assert calls == [upstream_release.UPSTREAM_RELEASE_API_URL, upstream_release.UPSTREAM_TAGS_API_URL]
    assert release.version == "v1.1.7"
    assert release.commit == "333c2b0c"


def test_fetch_latest_release_prefers_newer_tag_than_latest_release(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url == upstream_release.UPSTREAM_RELEASE_API_URL:
            payload = b'{"tag_name": "v1.1.2", "html_url": "https://example.test/v1.1.2", "assets": []}'
        else:
            assert request.full_url == upstream_release.UPSTREAM_TAGS_API_URL
            payload = b"""
            [
              {"name": "v1.1.7", "commit": {"sha": "333c2b0c"}},
              {"name": "v1.1.2", "commit": {"sha": "older"}}
            ]
            """
        return type(
            "Response",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_args: None,
                "read": lambda self: payload,
            },
        )()

    monkeypatch.setattr(upstream_release.urllib.request, "urlopen", fake_urlopen)

    release = upstream_release.fetch_latest_release()

    assert calls == [upstream_release.UPSTREAM_RELEASE_API_URL, upstream_release.UPSTREAM_TAGS_API_URL]
    assert release.version == "v1.1.7"
    assert release.commit == "333c2b0c"
