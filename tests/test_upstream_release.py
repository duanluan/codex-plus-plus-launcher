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
        if request.full_url == upstream_release.UPSTREAM_RELEASE_API_URL:
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

    assert calls == [upstream_release.UPSTREAM_RELEASE_API_URL, upstream_release.UPSTREAM_RELEASE_LATEST_URL]
    assert release.version == "v1.2.3"
    assert release.asset_url is None
    assert release.source_zip_url == f"https://github.com/{upstream_release.UPSTREAM_REPOSITORY}/archive/refs/tags/v1.2.3.zip"
