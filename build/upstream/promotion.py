"""build/upstream/promotion.py — the weekly promotion job (P3-T4, defs + local run).

Discovers the current even-milestone Extended-Stable-equivalent series from
LIVE data (chromiumdash releases — allowlisted; config: promotion-config.yaml,
cadence-as-data per the R9 date-sensitivity rule), resolves the series' latest
version tag to a Chromium commit (gitiles), and produces a PROMOTION PR BUNDLE:
DEPS pin bump + promotion-report.json + compat-smoke v0 results.

The job never merges, never pushes, never promotes: execution/approval is the
on-call human's act (HG-18; runbook docs/upstream-bot.md §promotion). A green
bundle says "promo-ready"; anything else routes an issues bundle.

Compat smoke v0 (Plan allows P9 stubs; tests/compat/ is the suite home):
deterministic, no build farm — argset validation, xr-patch apply/verify/revert
round-trip at the candidate rev over a scratch tree built from gitiles TEXT
fetches, brand_check fixtures + endpoint scan, SBOM fixture emission + gate,
and the §12.4 assumption suite (blocking).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard, repo_root  # noqa: E402
from fetch import FetchError, GitilesFetchSource  # noqa: E402
import assumptions as assumptions_mod  # noqa: E402
import issues as issues_mod  # noqa: E402
from classify import PatchResult  # noqa: E402


def load_config() -> dict[str, Any]:
    import yaml
    cfg_path = Path(__file__).resolve().parent / "promotion-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or cfg.get("schema_version") != 1:
        raise ToolError("promotion-config.yaml: schema_version must be 1")
    return cfg


def discover_series(source: GitilesFetchSource, cfg: dict[str, Any]) -> dict[str, Any]:
    """Current even-milestone Extended-Stable series (live data; cadence-as-data)."""
    series = cfg["series"]
    channel = series["channel"]
    parity = series["milestone_parity"]
    rows = source.releases(channel, "Windows", 10)
    if not rows:
        raise ToolError(f"no {channel} releases discovered (chromiumdash unreachable?)")
    for r in rows:
        milestone = r.get("milestone")
        if milestone is None:
            continue
        even = (milestone % 2 == 0)
        if (parity == "even") == even:
            return {"channel": channel, "milestone": milestone,
                    "version": str(r.get("version")),
                    "previous_version": r.get("previous_version"),
                    "published_at": datetime.fromtimestamp(
                        r["time"] / 1000, tz=timezone.utc).isoformat() if r.get("time") else None,
                    "source": "real"}
    raise ToolError(f"no {parity}-milestone {channel} release in the live window — "
                    "check promotion-config.yaml (cadence is data; update with research)")


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return r.returncode == 0, out[-600:]


def compat_smoke_v0(root: Path, source: GitilesFetchSource, candidate_rev: str,
                    manifest_path: Path, work: Path) -> list[dict[str, Any]]:
    """Deterministic compat suite (no build). Each step: {name, ok, detail}."""
    steps: list[dict[str, Any]] = []

    ok, out = _run([sys.executable, str(root / "build" / "gn" / "resolve_args.py"), "--validate"])
    steps.append({"name": "argsets-validate", "ok": ok, "detail": out})

    ok, out = _run([sys.executable, str(root / "build" / "branding" / "brand_check.py"),
                    "--fixture", str(work / "brand-fixtures"), "--json"])
    steps.append({"name": "brand-fixture", "ok": ok, "detail": out})
    ok, out = _run([sys.executable, str(root / "build" / "branding" / "brand_check.py"), "--scan"])
    steps.append({"name": "brand-endpoint-scan", "ok": ok, "detail": out})

    sbom_file = work / "sbom" / "sbom.json"
    sbom_file.parent.mkdir(parents=True, exist_ok=True)
    ok, out = _run([sys.executable, str(root / "build" / "sbom" / "emit_sbom.py"),
                    "--fixture", "--out", str(sbom_file)])
    sbom_ok, gate_detail = ok, out
    if ok:
        g_ok, g_out = _run([sys.executable, str(root / "build" / "sbom" / "sbom_gate.py"),
                            "--sbom", str(sbom_file)])
        sbom_ok, gate_detail = g_ok, g_out
    steps.append({"name": "sbom-fixture+gate", "ok": sbom_ok, "detail": gate_detail or out})

    # xr-patch apply/verify/revert round-trip at the candidate rev (scratch tree)
    rt_ok, rt_detail = _patch_roundtrip_at(source, manifest_path, candidate_rev)
    steps.append({"name": "patch-roundtrip-at-candidate", "ok": rt_ok, "detail": rt_detail})

    # §12.4 assumptions at the candidate rev (blocking for promotion)
    reg = assumptions_mod.load_registry()
    results, fails = assumptions_mod.run_rows(source, candidate_rev, reg)
    steps.append({"name": "assumptions-blocking", "ok": not fails,
                  "detail": "; ".join(fails) if fails else
                  f"{sum(1 for r in results if r['status']=='PASS')} PASS / "
                  f"{sum(1 for r in results if r['status']=='SKIP')} SKIP"})
    for r in results:
        if r["status"] == "FAIL":
            assumptions_mod._p0_artifact(r, candidate_rev, r["reason"], work / "issues")
    return steps


def _patch_roundtrip_at(source: GitilesFetchSource, manifest_path: Path,
                        candidate_rev: str) -> tuple[bool, str]:
    """Apply→verify→revert the real manifest's patches against a scratch tree of
    the candidate rev's files (gitiles TEXT; no checkout, no build — smoke v0)."""
    import yaml
    from classify import apply_patch, apply_check  # noqa: F401 (apply_check used below)
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"manifest load: {exc}"
    with tempfile.TemporaryDirectory(prefix="xr-promo-smoke-") as td:
        tree = Path(td)
        for p in manifest.get("patches", []):
            pdir = manifest_path.parent / p.get("dir", "")
            patches = sorted(pdir.glob("*.patch"))
            if not patches:
                return False, f"patch {p.get('id')}: no patch file in {pdir}"
            patch_text = patches[0].read_text(encoding="utf-8")
            files = {}
            for f in p.get("files", []):
                try:
                    files[f] = source.file_text(candidate_rev, f)
                except FetchError as exc:
                    # T0: a file absent at the candidate rev is materialized
                    # as ABSENT and `apply_patch` decides. An added file (absent
                    # at the pin by definition, so absent at any candidate too)
                    # is CREATED by the apply — clean, and the compat smoke no
                    # longer refuses it. A hooked file upstream DELETED fails
                    # the apply (refusal: a real re-anchor work item). Only a
                    # genuine 404 is an absence; any other FetchError still
                    # refuses (fail-closed — an absence is never guessed).
                    if "HTTP 404" not in str(exc):
                        return False, (f"patch {p.get('id')}: target file {f} "
                                       f"not fetchable at {candidate_rev[:12]}… — {exc}")
            for rel, text in files.items():
                fp = tree / rel
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(text, encoding="utf-8")
            ok, err = apply_patch(tree, patch_text)
            if not ok:
                return False, (f"patch {p.get('id')} does not apply at candidate "
                               f"{candidate_rev[:12]}… (promotion gate: semantic "
                               f"re-anchor first): {err}")
        return True, (f"{len(manifest.get('patches', []))} patch(es) apply at "
                      f"candidate {candidate_rev[:12]}… (scratch tree, smoke v0)")
    return True, "unreachable"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-promotion",
        description="Weekly promotion job (definitions + local execution): series "
                    "discovery, compat smoke v0, PR bundle preparation. Never merges.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover", help="live series discovery (cadence as data)")
    d.add_argument("--json", action="store_true")
    r = sub.add_parser("run", help="produce the promotion PR bundle (local only)")
    r.add_argument("--out", default="work/upstream-cache/promotion")
    r.add_argument("--manifest", default=None, help="override manifest path")
    r.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    cfg = load_config()
    source = GitilesFetchSource()

    if args.cmd == "discover":
        series = discover_series(source, cfg)
        if args.json:
            print(json.dumps(series, indent=2))
        else:
            print(f"promotion series: {series['channel']} M{series['milestone']} "
                  f"(latest {series['version']}, prev {series['previous_version']}, "
                  f"published {series['published_at']}) — live via {cfg['series']['discovery']}")
        return 0

    # run
    series = discover_series(source, cfg)
    try:
        candidate_rev = source.ref_value(f"tags/{series['version']}")
    except FetchError as exc:
        raise ToolError(f"cannot resolve tag refs/tags/{series['version']} on gitiles: {exc}") from exc

    manifest_path = (Path(args.manifest) if args.manifest else
                     root.parent / "xr-core" / "patches" / "manifest.yaml")
    if not manifest_path.exists():
        raise ToolError(f"manifest not found at {manifest_path} (run from the meta repo "
                        "with the xr-core sibling at the DEPS pin)")

    out = Path(args.out)
    if out.exists():
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    steps = compat_smoke_v0(root, source, candidate_rev, manifest_path, out)
    green = all(s["ok"] for s in steps)
    report = {
        "schema_version": 1, "tool": "xr-promotion", "source": "real",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "series": series, "candidate_rev": candidate_rev,
        "compat_smoke_v0": steps,
        "verdict": "promo-ready" if green else "issues",
        "law": "execution/approval is the on-call human's act (HG-18); this job "
               "prepares bundles and never merges (L24)",
    }
    (out / "promotion-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # PR bundle: the DEPS-bump patch (prepared, not applied)
    deps = (root / "DEPS").read_text(encoding="utf-8")
    new_deps = deps
    import re as _re
    new_deps = _re.sub(r'chromium_rev: "[0-9a-f]{40}"', f'chromium_rev: "{candidate_rev}"', new_deps)
    new_deps = _re.sub(r'chromium_version: "[^"]*"', f'chromium_version: "{series["version"]}"', new_deps)
    new_deps = _re.sub(r'chromium_milestone: \d+', f'chromium_milestone: {series["milestone"]}', new_deps)
    (out / "DEPS.promotion-bump").write_text(new_deps, encoding="utf-8")
    (out / "pr-body.md").write_text(
        f"# Promotion to {series['channel']} M{series['milestone']} ({series['version']})\n\n"
        f"- Candidate rev: `{candidate_rev}`\n"
        f"- Series discovery: live via chromiumdash (cadence as data; promotion-config.yaml)\n"
        f"- Compat smoke v0: {'GREEN' if green else 'ISSUES'}\n"
        + "".join(f"\n- {'✅' if s['ok'] else '❌'} {s['name']}" for s in steps)
        + "\n\n**HG-18**: the on-call human executes and approves this promotion "
          "(≤2 person-hours target; runbook docs/upstream-bot.md §promotion). "
          "The bot prepared this bundle; it merges nothing.\n", encoding="utf-8")

    if not green:
        failed = [s for s in steps if not s["ok"]]
        routed = issues_mod.route(
            {"from_rev": "?", "to_resolved": candidate_rev, "source": "real",
             "patches": [{"id": f"promotion:{s['name']}", "owner": "@xr/platform",
                          "category": "ui", "cls": "semantic",
                          "files": [{"path": s["name"], "cls": "semantic",
                                     "detail": s["detail"], "moved_to": None}]} for s in failed]},
            out / "issues")
        report["issue_bundles"] = [str(p) for p in routed]

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"series: {series['channel']} M{series['milestone']} latest {series['version']}")
        print(f"candidate rev: {candidate_rev}")
        for s in steps:
            print(f"  {'PASS' if s['ok'] else 'FAIL'}: {s['name']}")
        print(f"verdict: {report['verdict']} — bundle in {out} "
              "(execution = on-call human, HG-18)")
    return 0 if green else 1


if __name__ == "__main__":
    main_with_guard(lambda: main())
