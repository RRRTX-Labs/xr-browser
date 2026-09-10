"""build/upstream/fetch.py — the ONE network choke point for upstream tracking (P3-T1).

House law (phase prompt, Codebase requirements): "Network calls ONLY through
build/upstream/fetch.py (single choke point — grep-enforced)" — enforced by
tools/fetch_allowlist_check.py in CI.

Security model:
  - https-only, exact-host allowlist enforced IN CODE (no config weakening):
      chromium.googlesource.com        (gitiles JSON/TEXT/archive APIs — R1)
      commondatastorage.googleapis.com (toolchain/host artifacts)
      chromiumdash.appspot.com         (milestone/release truth — R3)
      api.github.com                   (optional issue-bot surface, HG-16)
  - redirects are validated hop-by-hop: a redirect out of the allowlist is
    refused (test-covered, including a mock server that tries).
  - read-only: GET only; the module has no write/push/credential path and
    writes nothing outside work/upstream-cache/ (the disk cache).
  - fail-closed with bounded transient retry: a genuine 404 / non-allowlisted
    host / bad-redirect fails on the FIRST attempt (never retried); only a
    transient network blip or 5xx is retried (3 attempts, backoff) before
    failing closed — a retry can never turn a failure into a pass.
  - gitiles content at an immutable rev is cached forever under
    work/upstream-cache/http/; mutable endpoints (branch logs, chromiumdash
    releases) are never cached.

Offline/testing: FixtureFetchSource serves the same interface from a dict —
all engine tests run offline; live runs use GitilesFetchSource.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Protocol

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard  # noqa: E402

ALLOWED_HOSTS: frozenset[str] = frozenset({
    "chromium.googlesource.com",
    "commondatastorage.googleapis.com",
    "chromiumdash.appspot.com",
    "api.github.com",
})
CHROMIUM_GITILES = "https://chromium.googlesource.com/chromium/src"
CHROMIUMDASH = "https://chromiumdash.appspot.com"
FETCH_TIMEOUT_S = 30
USER_AGENT = "xr-browser-upstream-bot/1.0 (read-only; +rrrtx-labs/xr-browser)"


class FetchError(ToolError):
    """Network/allowlist failure. Fail-closed: a genuine error (404,
    non-allowlisted host, bad redirect) is raised on the first attempt and is
    never retried or masked. Only transient network/5xx blips are retried
    (bounded) before failing closed — a retry can never turn a failure into a
    pass."""


def assert_url_allowed(url: str) -> None:
    """Enforce https + exact-host allowlist. Raises FetchError otherwise."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise FetchError(f"unparseable URL {url!r}: {exc}") from exc
    if parts.scheme != "https":
        raise FetchError(f"non-https URL refused: {url!r} (https-only policy)")
    if parts.hostname not in ALLOWED_HOSTS:
        raise FetchError(
            f"host {parts.hostname!r} not on the fetch allowlist "
            f"(allowed: {sorted(ALLOWED_HOSTS)}); refusing {url!r}")


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Validate every redirect hop against the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        assert_url_allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_AllowlistRedirectHandler())

# Bounded retry for TRANSIENT blips only — a shared-CI gitiles hiccup (dropped
# connection, timeout, 5xx) must not red the governance gate. Genuine failures
# (HTTP 4xx, a redirect/allowlist FetchError, a decode error) still fail CLOSED
# on the first attempt: retry never masks a real failure, it only survives a
# momentary blip, and it gives up (fail-closed) after _HTTP_MAX_ATTEMPTS.
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504})
_HTTP_MAX_ATTEMPTS = 3
_HTTP_BACKOFF_S = (0.5, 2.0)  # sleep before attempt 2, then before attempt 3


def http_get(url: str, *, timeout: int = FETCH_TIMEOUT_S) -> bytes:
    """Allowlisted, redirected-checked GET. The only network call in the tree.

    Transient errors (connection reset/timeout, HTTP 408/429/5xx) are retried
    with backoff and then fail closed; genuine errors (404, a non-allowlisted
    host, a bad redirect) fail immediately."""
    assert_url_allowed(url)  # allowlist enforced once, up front (never retried)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(_HTTP_MAX_ATTEMPTS):
        if attempt:
            time.sleep(_HTTP_BACKOFF_S[attempt - 1])
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP:
                raise FetchError(f"HTTP {exc.code} fetching {url}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
    raise FetchError(
        f"fetch failed for {url} after {_HTTP_MAX_ATTEMPTS} attempts: {last}")


class CiRunNotFound(FetchError):
    """The run/job id resolves to nothing (HTTP 404) — a real red, not a skip."""


def resolve_ci_run(run_id: int, job_id: int, *,
                   org: str = "RRRTX-Labs", repo: str = "xr-browser",
                   timeout: int = FETCH_TIMEOUT_S) -> dict[str, Any]:
    """Resolve a hosted-CI run + job through the ONLY network path (P9-T12).

    Feeds tools/evidence_check.py's machine-side "green" rule: a `ci-run`
    evidence row is certifiable only when the job concluded `success` and the
    run's `head_sha` is a commit the bundle records. Read-only, https-only,
    api.github.com already allowlisted. A genuine 404 raises CiRunNotFound
    (fail-closed: a cited run that does not exist is a red, never a skip);
    a network/transient failure raises FetchError (the caller turns that into
    a visible SKIP — offline is not the same as fabricated).
    """
    run_url = f"https://api.github.com/repos/{org}/{repo}/actions/runs/{run_id}"
    job_url = f"https://api.github.com/repos/{org}/{repo}/actions/jobs/{job_id}"
    try:
        run_raw = http_get(run_url, timeout=timeout)
        job_raw = http_get(job_url, timeout=timeout)
    except FetchError as exc:
        if "HTTP 404" in str(exc):
            raise CiRunNotFound(
                f"ci run {run_id} (job {job_id}) not found: {exc}") from exc
        raise
    run = json.loads(run_raw)
    job = json.loads(job_raw)
    return {
        "conclusion": job.get("conclusion"),
        "status": run.get("status"),
        "head_sha": run.get("head_sha"),
        "name": run.get("name"),
        "html_url": run.get("html_url"),
    }


def _strip_magic(raw: bytes) -> bytes:
    """gitiles JSON responses start with the XSSI guard line )]}' — strip it."""
    if raw.startswith(b")]}'"):
        return raw.split(b"\n", 1)[1]
    return raw


class FetchSource(Protocol):
    """The upstream-data interface every P3 engine consumes (offline-testable)."""

    def file_text(self, rev: str, path: str) -> str: ...
    def dir_listing(self, rev: str, path: str) -> list[str]: ...
    def log(self, ref: str, n: int, *, start: str | None = None) -> list[dict[str, Any]]: ...
    def commit(self, rev: str) -> dict[str, Any]: ...
    def ref_value(self, ref: str) -> str: ...
    def releases(self, channel: str, platform: str, num: int) -> list[dict[str, Any]]: ...


class GitilesFetchSource:
    """Live source: gitiles JSON/TEXT + chromiumdash releases, with a
    content-addressed cache for immutable-rev data under work/upstream-cache/."""

    def __init__(self, cache_root: Path | None = None) -> None:
        self.cache_root = cache_root or Path("work") / "upstream-cache" / "http"
        self.bytes_fetched = 0
        self.requests = 0

    # -- cache helpers ----------------------------------------------------
    def _cached(self, url: str, *, immutable: bool) -> bytes:
        if immutable:
            key = hashlib.sha256(url.encode()).hexdigest()
            cpath = self.cache_root / key
            if cpath.exists():
                return cpath.read_bytes()
        data = http_get(url)
        self.bytes_fetched += len(data)
        self.requests += 1
        if immutable:
            self.cache_root.mkdir(parents=True, exist_ok=True)
            cpath = self.cache_root / key
            cpath.write_bytes(data)
        return data

    # -- gitiles ----------------------------------------------------------
    def file_text(self, rev: str, path: str) -> str:
        url = f"{CHROMIUM_GITILES}/+/{rev}/{path}?format=TEXT"
        raw = self._cached(url, immutable=True)
        try:
            return base64.b64decode(raw).decode("utf-8")
        except Exception as exc:  # decode of upstream data
            raise FetchError(f"gitiles TEXT decode failed for {rev}/{path}: {exc}") from exc

    def dir_listing(self, rev: str, path: str) -> list[str]:
        url = f"{CHROMIUM_GITILES}/+/{rev}/{path}/?format=JSON"
        raw = _strip_magic(self._cached(url, immutable=True))
        data = json.loads(raw)
        return [e["name"] for e in data.get("entries", [])]

    def log(self, ref: str, n: int, *, start: str | None = None) -> list[dict[str, Any]]:
        base = f"{CHROMIUM_GITILES}/+log/{ref}"
        if start:
            base = f"{CHROMIUM_GITILES}/+log/{start}..{ref}"
        url = f"{base}?format=JSON&n={n}"
        raw = _strip_magic(self._cached(url, immutable=False))
        return json.loads(raw).get("log", [])

    def commit(self, rev: str) -> dict[str, Any]:
        url = f"{CHROMIUM_GITILES}/+/{rev}?format=JSON"
        raw = _strip_magic(self._cached(url, immutable=True))
        return json.loads(raw)

    def ref_value(self, ref: str) -> str:
        url = f"{CHROMIUM_GITILES}/+refs/{ref}?format=JSON"
        raw = _strip_magic(self._cached(url, immutable=ref.startswith("tags/")))
        data = json.loads(raw)
        entry = data.get(f"refs/{ref}")
        if not entry:
            raise FetchError(f"ref refs/{ref} not found on gitiles")
        return entry["value"]

    # -- chromiumdash -----------------------------------------------------
    def releases(self, channel: str, platform: str, num: int) -> list[dict[str, Any]]:
        url = f"{CHROMIUMDASH}/fetch_releases?channel={urllib.parse.quote(channel)}&platform={urllib.parse.quote(platform)}&num={num}"
        raw = self._cached(url, immutable=False)
        return json.loads(raw)


class FixtureFetchSource:
    """Deterministic offline source (tests + drills). `files` maps
    (rev, path) -> text; optional `logs`, `refs`, `commits`, `release_rows`."""

    def __init__(self, files: dict[tuple[str, str], str] | None = None,
                 dirs: dict[tuple[str, str], list[str]] | None = None,
                 logs: dict[str, list[dict[str, Any]]] | None = None,
                 refs: dict[str, str] | None = None,
                 commits: dict[str, dict[str, Any]] | None = None,
                 release_rows: list[dict[str, Any]] | None = None) -> None:
        self._files = files or {}
        self._dirs = dirs or {}
        self._logs = logs or {}
        self._refs = refs or {}
        self._commits = commits or {}
        self._releases = release_rows or []
        self.bytes_fetched = sum(len(v.encode()) for v in self._files.values())
        self.requests = len(self._files)

    def file_text(self, rev: str, path: str) -> str:
        try:
            return self._files[(rev, path)]
        except KeyError:
            raise FetchError(f"HTTP 404 fetching fixture {rev}/{path}") from None

    def dir_listing(self, rev: str, path: str) -> list[str]:
        return self._dirs.get((rev, path), [])

    def log(self, ref: str, n: int, *, start: str | None = None) -> list[dict[str, Any]]:
        if start:
            return self._logs.get(f"{start}..{ref}", self._logs.get(ref, []))[:n]
        return self._logs.get(ref, [])[:n]

    def commit(self, rev: str) -> dict[str, Any]:
        try:
            return self._commits[rev]
        except KeyError:
            raise FetchError(f"fixture commit {rev} not found") from None

    def ref_value(self, ref: str) -> str:
        try:
            return self._refs[ref]
        except KeyError:
            raise FetchError(f"ref refs/{ref} not found in fixtures") from None

    def releases(self, channel: str, platform: str, num: int) -> list[dict[str, Any]]:
        rows = [r for r in self._releases if r.get("channel") == channel
                and r.get("platform") in (platform, "All")]
        return rows[:num]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="upstream-fetch",
        description="Allowlisted read-only upstream fetcher (choke point). "
                    "Subcommands are diagnostics; engines import the classes.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check-url", help="validate one URL against the allowlist")
    chk.add_argument("url")
    probe = sub.add_parser("probe", help="live reachability probe (env evidence)")
    probe.add_argument("--rev", default="refs/heads/main")
    args = parser.parse_args()

    if args.cmd == "check-url":
        try:
            assert_url_allowed(args.url)
        except FetchError as exc:
            print(f"REFUSED: {exc}")
            return 1
        print(f"ALLOWED: {args.url}")
        return 0

    if args.cmd == "probe":
        src = GitilesFetchSource()
        t0 = time.monotonic()
        log = src.log(args.rev, 1)
        el = time.monotonic() - t0
        tip = log[0]["commit"] if log else "<none>"
        print(f"gitiles {args.rev} tip: {tip} ({el:.2f}s, {src.bytes_fetched} B)")
        rel = src.releases("Stable", "Windows", 1)
        if rel:
            r = rel[0]
            print(f"chromiumdash Stable: {r.get('version')} (M{r.get('milestone')}, prev {r.get('previous_version')})")
        print("PROBE OK")
        return 0
    return 2


if __name__ == "__main__":
    main_with_guard(lambda: main())
