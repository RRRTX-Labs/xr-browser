"""build/upstream/fastlane_drills.py — the synthetic security drills (P3-T5).

Split from fastlane.py (<400 LOC law): fixture security repo + run_drill —
the end-to-end rehearsal detect→plan→apply→verify→sign(P2, TEST keys)→SLA→
freeze-on-breach→report. Every artifact: source:"fixture", SIMULATED,
elapsed_real_seconds vs simulated_elapsed_hours kept apart (honest-drill law).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from datetime import datetime, timedelta, timezone  # noqa: E402

from _common import ToolError  # noqa: E402
# safe: fastlane imports this module only LAZILY (PEP-562 __getattr__ +
# drill-time import), so fastlane is fully initialized whenever we load
from fastlane import (FixtureWatchSource, build_plan, classify_commits,  # noqa: E402
                      sla_clock, validate_plan, write_freeze_marker)


def _fixture_security_repo(root: Path) -> tuple[Path, str, str]:
    """A synthetic upstream repo with one 'security fix' commit (drill data).
    Returns (repo_path, pre_sha, fix_sha)."""
    import subprocess as sp
    repo = root / "fixture-upstream"
    repo.mkdir(parents=True, exist_ok=True)
    def g(*a):
        r = sp.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
        if r.returncode != 0:
            raise ToolError(f"fixture repo git {a[0]}: {r.stderr}")
        return r.stdout.strip()
    g("init", "-q"); g("config", "user.email", "fixture@xr.test"); g("config", "user.name", "fixture")
    (repo / "net_parser.cc").write_text(
        "int parse(const char* b) {\n  return b[0];  // pre-fix: unvalidated length\n}\n", encoding="utf-8")
    g("add", "-A"); g("commit", "-qm", "fixture: pre-fix state")
    pre = g("rev-parse", "HEAD")
    (repo / "net_parser.cc").write_text(
        "int parse(const char* b, int len) {\n  if (len <= 0) return -1;  // fix: validate (CVE-2026-99999 fixture)\n  return b[0];\n}\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-qm",
      "Security: validate length in net_parser (CVE-2026-99999)\n\nBug: b:999999999\n"
      "Reviewed-on: https://chromium-review.googlesource.com/c/chromium/src/+/9999999\n"
      "Cr-Commit-Position: refs/heads/fake-main@{#9999}")
    fix = g("rev-parse", "HEAD")
    return repo, pre, fix


def run_drill(*, out_dir: Path, root: Path, label: str,
              published_hours_ago: float, expect_breach: bool) -> dict[str, Any]:
    """One synthetic fast-lane drill: detect → plan → apply → verify → sign(test) → report.
    Everything is fixture data; every artifact carries source:"fixture" + SIMULATED."""
    import subprocess as sp
    import time as _time
    import shutil
    t0 = _time.monotonic()
    if out_dir.exists():  # drills are idempotent: always start from a clean dir
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    published = now - timedelta(hours=published_hours_ago)

    repo, pre, fix = _fixture_security_repo(out_dir)
    # stable-branch fixture repo to cherry-pick onto
    stable = out_dir / "fixture-stable-branch"
    sp.run(["git", "clone", "-q", str(repo), str(stable)], check=True, capture_output=True)
    sp.run(["git", "-C", str(stable), "checkout", "-q", pre], check=True, capture_output=True)
    sp.run(["git", "-C", str(stable), "config", "user.email", "drill@xr.test"], check=True, capture_output=True)
    sp.run(["git", "-C", str(stable), "config", "user.name", "fastlane-drill"], check=True, capture_output=True)

    # 1. detect (fixture watch source; invented CVE + tag date)
    watch = FixtureWatchSource([{
        "version": "150.0.7339.200-fixture", "channel": "Stable", "milestone": 150,
        "published_at": published.isoformat(), "previous_version": "150.0.7339.100-fixture",
        "chromium_hash": fix,
    }])
    releases = watch.poll()
    assert releases, "fixture watch produced no release"
    rel = releases[0]

    # 2. plan (advisory commit classification over the fixture fix commit)
    log = [{"commit": fix, "message": sp.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%B", fix],
        capture_output=True, text=True).stdout}]
    plan = build_plan(rel)
    plan["candidates"] = [vars(c) for c in classify_commits(log)]
    plan["drill"] = {"label": label, "simulated": True,
                     "published_hours_ago": published_hours_ago,
                     "note": "SIMULATED drill — invented CVE + tag dates (Plan §12.4 drill twice/year)"}
    fails = validate_plan(plan)
    if fails:
        raise ToolError("drill plan invalid: " + "; ".join(fails))
    plan_path = out_dir / f"cherry-pick-plan-{label}.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    # 3. apply: cherry-pick the fixture fix onto the stable-branch fixture repo
    r = sp.run(["git", "-C", str(stable), "cherry-pick", fix],
               capture_output=True, text=True)
    applied = r.returncode == 0
    apply_stderr = r.stderr.strip()[-300:]

    # 4. verify
    content = (stable / "net_parser.cc").read_text(encoding="utf-8")
    verified = "validate" in content and "CVE-2026-99999" in content

    # 5. sign the PLAN artifact through the P2 interface (TEST keys; dev channel)
    key = out_dir / "test-minisign.key"
    sp.run(["minisign", "-G", "-W", "-f", "-s", str(key), "-p", str(out_dir / "test-minisign.pub"),
            "-c", "XR DRILL TEST key (TEST-ONLY)"], check=True, capture_output=True)
    sign_r = sp.run(
        [sys.executable, str(root / "build" / "signing" / "sign_artifact.py"),
         "--artifact", str(plan_path), "--channel", "dev", "--os", "linux",
         "--key", str(key), "--out", str(out_dir / "sign")],
        capture_output=True, text=True)
    signed = sign_r.returncode == 0
    # negative: an unsigned stable/release path must be STRUCTURALLY refused
    neg = sp.run(
        [sys.executable, str(root / "build" / "signing" / "sign_artifact.py"),
         "--artifact", str(plan_path), "--channel", "stable", "--os", "linux",
         "--key", str(key), "--out", str(out_dir / "sign")],
        capture_output=True, text=True)
    unsigned_refused = neg.returncode != 0 and "refused" in (neg.stderr + neg.stdout).lower()

    # 6. SLA clock (simulated hours; measured from TAG PUBLICATION)
    clock = sla_clock(since_tag=rel.version, published_at=rel.published_at,
                      now=now, severity="critical")
    freeze = None
    if clock["breached"]:
        freeze = str(write_freeze_marker(out_dir, (
            f"simulated drill breach: {rel.version} published "
            f"{rel.published_at.isoformat()}, critical deadline "
            f"{clock['deadline']} missed by {-clock['remaining_hours']:.1f}h (SIMULATED)")))

    elapsed = round(_time.monotonic() - t0, 2)
    report = {
        "schema_version": 1, "tool": "xr-fastlane-drill", "source": "fixture",
        "label": label, "simulated": True,
        "steps": {"detect": "ok", "plan": str(plan_path),
                  "apply": "ok" if applied else "FAILED", "apply_stderr": apply_stderr if not applied else "",
                  "verify": "ok" if verified else "FAILED",
                  "sign_p2_dev_channel": "ok" if signed else "FAILED",
                  "unsigned_stable_refused": unsigned_refused,
                  "sla": clock, "freeze_marker": freeze},
        "elapsed_real_seconds": elapsed,
        "simulated_elapsed_hours": round(published_hours_ago, 1),
        "verdict": "PASS" if (applied and verified and signed and unsigned_refused
                              and clock["breached"] == expect_breach) else "FAIL",
    }
    (out_dir / f"drill-report-{label}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


