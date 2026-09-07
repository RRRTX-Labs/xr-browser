"""build/sync.py — `./scripts/build sync` and `./scripts/build refresh`.

sync: create a pinned Chromium checkout with xr-core mounted at `src/xr`,
      exactly the Brave overlay pattern (Plan §7.1, L24): a synthesized gclient
      config checks out Chromium at `chromium_rev` and clones xr-core at
      `xr_core_rev` into `src/xr`. Records an egress manifest
      (`<checkout>/.xr/egress.json`) — the checkable zero-egress property
      (build/net-audit.md).

refresh: `--to <sha>` — create branch `refresh/chromium-<n>`, update DEPS,
         run preflight (+ gn parse of argsets if a checkout exists), emit
         PR-body markdown with the L9 dependency-eval refresh reminder.
         NEVER auto-pushes (DoD: refresh is tested by branch creation only).

depot_tools is fetched at runtime (BSD-3, see docs/dependencies/depot-tools.yaml)
— never vendored. The mount uses gclient's documented `custom_deps` solution
field (README.gclient.md) — no novel mechanism.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import (
    ToolError,
    add_common_flags,
    emit,
    load_deps,
    main_with_guard,
    mock_enabled,
    repo_root,
)

CHROMIUM_URL = "https://chromium.googlesource.com/chromium/src.git"
XR_CORE_URL = "https://github.com/RRRTX-Labs/xr-core.git"
DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GCLIENT_TPL = """\
solutions = [
  {{
    "name": "src",
    "url": "{chromium}",
    "deps_file": "DEPS",
    "custom_deps": {{
      "src/xr": "{xr}",
    }},
  }},
]
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _checkout_root(args: argparse.Namespace) -> Path:
    return Path(args.checkout).resolve() if getattr(args, "checkout", None) else Path.cwd() / "chromium"


def _is_checkout(root: Path) -> bool:
    # gclient solution "name": "src" -> chromium at <root>/src, xr-core at <root>/src/xr
    return (root / "src" / "chrome" / "VERSION").exists() and (root / "src" / "xr" / ".git").exists()


def synthesize_gclient(deps: dict[str, Any]) -> str:
    cr = deps.get("chromium_rev")
    xr = deps.get("xr_core_rev")
    scheme = deps.get("gclient_url_scheme", "https")
    if not SHA_RE.match(str(cr)) or not SHA_RE.match(str(xr)):
        raise ToolError("DEPS: chromium_rev/xr_core_rev must be 40-char SHAs")
    if scheme != "https":
        raise ToolError(f"DEPS: gclient_url_scheme must be 'https' (got {scheme!r}); pinned https remotes only")
    return GCLIENT_TPL.format(chromium=f"{CHROMIUM_URL}@{cr}", xr=f"{XR_CORE_URL}@{xr}")


def find_depot_tools(root: Path) -> Path:
    """Return a depot_tools checkout, fetching at runtime if absent."""
    dt = root / ".xr" / "depot_tools"
    if not (dt / "gclient").exists():
        if mock_enabled():
            print("MOCK MODE — not a build: would fetch depot_tools")
            dt.mkdir(parents=True, exist_ok=True)
        else:
            dt.parent.mkdir(parents=True, exist_ok=True)
            r = _git(dt.parent, "clone", "--depth", "1", DEPOT_TOOLS_URL, str(dt))
            if r.returncode != 0:
                raise ToolError(f"depot_tools fetch failed: {r.stderr.strip()}")
    return dt


def record_egress(root: Path, deps: dict[str, Any]) -> Path:
    xr_dir = root / ".xr"
    xr_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "synced_at": _now(),
        "chromium_rev": deps["chromium_rev"],
        "xr_core_rev": deps["xr_core_rev"],
        "contacts": [
            {"url": CHROMIUM_URL, "purpose": "solution checkout", "at": _now()},
            {"url": XR_CORE_URL, "purpose": "mount src/xr", "at": _now()},
            {"url": DEPOT_TOOLS_URL, "purpose": "runtime tool fetch", "at": _now()},
        ],
    }
    p = xr_dir / "egress.json"
    p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return p


def cmd_sync(args: argparse.Namespace) -> int:
    root = repo_root()
    deps = load_deps(root)
    checkout = _checkout_root(args)
    gclient = synthesize_gclient(deps)

    failures: list[str] = []
    if _is_checkout(checkout) and not args.force:
        failures.append(
            f"{checkout} already looks like a checkout (chrome/VERSION + src/xr); "
            "use --force to re-sync (never runs `git clean`; see build/net-audit.md)"
        )
    if failures and not args.force:
        return emit(args.json, {"tool": "sync", "checkout": str(checkout)}, failures=failures)

    # Preflight (refuse under-provisioned machines; never simulate state).
    if not mock_enabled():
        from preflight import check_disk
        ok, msg = check_disk(checkout, estimate_gb=120.0)
        if not ok:
            return emit(args.json, {"tool": "sync", "preflight": msg}, failures=[msg])

    dt = find_depot_tools(checkout)
    gclient_file = checkout / ".gclient"
    checkout.mkdir(parents=True, exist_ok=True)
    gclient_file.write_text(gclient, encoding="utf-8")

    if mock_enabled():
        print("MOCK MODE — not a build: would run gclient sync (no checkout performed)")
        egress = record_egress(checkout, deps)
        return emit(args.json, {
            "tool": "sync", "mode": "mock", "checkout": str(checkout),
            "gclient": str(gclient_file), "egress": str(egress),
        })

    gclient_bin = dt / "gclient"
    extra = ["--nohooks"] if args.nohooks else []
    if args.shallow:
        extra.append("--shallow")
    r = subprocess.run(
        [sys.executable, str(gclient_bin), "sync", *extra],
        cwd=checkout, text=True,
    )
    if r.returncode != 0:
        return emit(args.json, {"tool": "sync", "checkout": str(checkout)},
                    failures=[f"gclient sync failed ({r.returncode}); see output above"])

    # Verify the mount: xr-core must be present at src/xr at the pinned rev.
    xr = checkout / "src" / "xr"
    if not (xr / ".git").exists():
        return emit(args.json, {"tool": "sync", "checkout": str(checkout)},
                    failures=[f"mount missing: {xr} is not a git checkout"])
    r = _git(xr, "rev-parse", "HEAD")
    if r.stdout.strip() != deps["xr_core_rev"]:
        return emit(args.json, {"tool": "sync", "checkout": str(checkout)},
                    failures=[f"mount mismatch: src/xr HEAD={r.stdout.strip()!r} expected {deps['xr_core_rev']!r}"])

    egress = record_egress(checkout, deps)
    return emit(args.json, {
        "tool": "sync", "checkout": str(checkout),
        "chromium_rev": deps["chromium_rev"], "xr_core_rev": deps["xr_core_rev"],
        "egress": str(egress),
    })


def cmd_check_pin_alive(args: argparse.Namespace) -> int:
    """`./scripts/build sync --check-pin-alive` (P4-T0.2).

    The DEPS `xr_core_rev` is a cross-repo pin: it must be a commit that is
    actually reachable from origin xr-core `main`. A pin pointing at a
    rewritten/unpushed commit breaks every fresh clone (build + CI), so this
    is a blocking lint, not an advisory.

    Method (unauthenticated, public remotes only — no credentials, no token):
      1. `git ls-remote <origin> refs/heads/main`  -> origin HEAD sha
      2. scratch `git init` + `git fetch --no-tags origin main`
      3. `git merge-base --is-ancestor <pinned_rev> FETCH_HEAD` -> reachability

    Failure is fail-closed: unreachable/unresolvable => exit 1 with the
    reason. Never a silent pass, never simulated from remembered SHAs.
    """
    root = repo_root()
    deps = load_deps(root)
    rev = str(deps.get("xr_core_rev") or "")
    if not SHA_RE.match(rev):
        raise ToolError(f"DEPS: xr_core_rev is not a 40-char SHA (got {rev!r})")
    url = getattr(args, "remote", None) or XR_CORE_URL
    if not url.startswith("https://"):
        raise ToolError(f"xr-core remote must be https (got {url!r})")

    def _gitq(*a: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *a], cwd=str(cwd) if cwd else None,
                              text=True, capture_output=True)

    ls = _gitq("ls-remote", url, "refs/heads/main")
    if ls.returncode != 0:
        raise ToolError(f"pin-alive: git ls-remote {url} failed: {ls.stderr.strip()}")
    if not ls.stdout.strip():
        raise ToolError(f"pin-alive: {url} has no refs/heads/main (repo moved/renamed?)")
    origin_main = ls.stdout.split()[0]

    with tempfile.TemporaryDirectory(prefix="xr-pin-alive-") as tmp:
        scratch = Path(tmp) / "probe"
        scratch.mkdir()
        _gitq("init", "-q", cwd=scratch)
        _gitq("remote", "add", "origin", url, cwd=scratch)
        f = _gitq("fetch", "-q", "--no-tags", "origin", "main", cwd=scratch)
        if f.returncode != 0:
            raise ToolError(f"pin-alive: fetch of origin main failed: {f.stderr.strip()}")
        fetch_rev = _gitq("fetch", "-q", "--no-tags", "origin", rev, cwd=scratch)
        object_present = fetch_rev.returncode == 0
        ancestor = False
        if object_present:
            anc = _gitq("merge-base", "--is-ancestor", rev, "FETCH_HEAD", cwd=scratch)
            ancestor = anc.returncode == 0

    failures: list[str] = []
    if not object_present:
        failures.append(
            f"DEPS xr_core_rev {rev} is not fetchable from {url} "
            f"(unpushed, force-pushed away, or the pin was never pushed)")
    elif not ancestor:
        failures.append(
            f"DEPS xr_core_rev {rev} is fetchable but is NOT an ancestor of "
            f"origin main ({origin_main}) — diverged or rewritten history")

    return emit(args.json, {
        "tool": "check-pin-alive",
        "pinned_rev": rev,
        "origin_main": origin_main,
        "remote": url,
        "object_present": object_present,
        "ancestor_of_main": ancestor,
        "verified_by": "git ls-remote + fetch + merge-base --is-ancestor",
        "auth": "unauthenticated (public repo, no token)",
        "source": "real-fetch",
    }, failures=failures)


def cmd_refresh(args: argparse.Namespace) -> int:
    root = repo_root()
    deps = load_deps(root)
    target = args.to
    if not SHA_RE.match(target):
        raise ToolError(f"--to must be a 40-char SHA (got {target!r})")
    if target == deps["chromium_rev"]:
        raise ToolError(f"already pinned at {target}")

    r = _git(root, "status", "--porcelain")
    if r.stdout.strip():
        raise ToolError("working tree is dirty; commit or stash before refresh")

    # Branch refresh/chromium-<n> — never re-used.
    r = _git(root, "branch", "--list", "refresh/chromium-*")
    n = 1
    existing = set(r.stdout.split())
    while f"refresh/chromium-{n}" in existing:
        n += 1
    branch = f"refresh/chromium-{n}"
    if mock_enabled():
        print(f"MOCK MODE — not a build: would create branch {branch}")
    else:
        r = _git(root, "checkout", "-b", branch)
        if r.returncode != 0:
            raise ToolError(f"branch creation failed: {r.stderr.strip()}")

    # Update DEPS in place (the only pin writer).
    deps_path = root / "DEPS"
    text = deps_path.read_text(encoding="utf-8")
    new_text = re.sub(
        r'(chromium_rev:\s*")[0-9a-f]{40}(")',
        rf'\g<1>{target}\g<2>', text, count=1,
    )
    if new_text == text:
        raise ToolError("DEPS: could not locate chromium_rev line to update")
    if mock_enabled():
        print("MOCK MODE — not a build: would write DEPS chromium_rev update")
    else:
        deps_path.write_text(new_text, encoding="utf-8")

    pr_body = (
        f"## Chromium pin refresh → `{target}`\n\n"
        f"- Branch: `{branch}`\n"
        f"- From: `{deps['chromium_rev']}`\n"
        f"- To: `{target}`\n\n"
        "**Pre-flight:** `./scripts/build preflight`\n"
        "**Argset check:** if a checkout exists at this rev, run "
        "`./scripts/build gen --checkout <dir> --argset xr_release` (gn parse).\n\n"
        "**Dependency-eval refresh reminder (Plan L9):** any dependency whose "
        "90-day `refresh_by` has passed must be re-evaluated in this same PR. "
        "Do not merge a pin refresh that leaves stale evals.\n\n"
        "Never auto-pushed; push when human-approved.\n"
    )
    out = root / ".xr" / f"refresh-{branch}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pr_body, encoding="utf-8")
    return emit(args.json, {
        "tool": "refresh", "branch": branch, "from": deps["chromium_rev"], "to": target,
        "pr_body": str(out),
    })


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build/sync.py",
        description="Sync a pinned Chromium checkout with xr-core mounted at src/xr; or refresh the pin.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="create/verify the pinned checkout")
    p_sync.add_argument("--checkout", help="checkout directory (default: ./chromium)")
    p_sync.add_argument("--shallow", action="store_true", help="pass --shallow to gclient")
    p_sync.add_argument("--nohooks", action="store_true", help="pass --nohooks to gclient")
    p_sync.add_argument("--force", action="store_true", help="re-sync an existing checkout")

    p_refresh = sub.add_parser("refresh", help="create a pin-refresh branch (never pushes)")
    p_refresh.add_argument("--to", required=True, help="target 40-char chromium SHA")

    p_alive = sub.add_parser("check-pin-alive",
                             help="verify DEPS xr_core_rev is reachable from origin xr-core main")
    p_alive.add_argument("--remote", default=XR_CORE_URL,
                         help="xr-core remote (default: the org repo; https only)")

    add_common_flags(parser)
    for sp in (p_sync, p_refresh, p_alive):
        sp.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()
    if args.cmd == "sync":
        main_with_guard(lambda: cmd_sync(args))
    elif args.cmd == "check-pin-alive":
        main_with_guard(lambda: cmd_check_pin_alive(args))
    else:
        main_with_guard(lambda: cmd_refresh(args))


if __name__ == "__main__":
    main()
