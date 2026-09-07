"""build/upstream/rebase_bot.py — `./scripts/build rebase` (P3-T1).

Daily-canary rebase *classification* engine (Plan §12.1). For each xr-core
patch: fetch pin/target file contents through the allowlisted choke point
(zero-clone gitiles TEXT — research R2), classify applicability per §12.3
(classes in classify.py), route conflicts to owner bundles (issues.py), and
emit rebase-report.json v1 (contract: docs/contracts/patch-ledger-v1.md).

Safety laws implemented here:
  - read-only upstream (fetch.py); zero write/push paths — the only local
    writes are work/upstream-cache/** and, on a GREEN non-dry run, a LOCAL
    candidate DEPS-bump branch created with git plumbing (never checked out,
    never pushed — L24: humans press the button).
  - conflicts are work items: routed bundles, never auto-"fixed".
  - every report row carries source: real|fixture (validator-enforced).
  - wall-clock meter (Plan §4 P3 Perf: ≤ 8 h end-to-end budget).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, load_deps, main_with_guard, repo_root  # noqa: E402
from classify import (  # noqa: E402
    CLASS_DELETED, PatchResult, classify_patch, next_action,
    validate_rebase_report, verdict_of,
)
from fetch import FetchError, GitilesFetchSource  # noqa: E402
import issues as issues_mod  # noqa: E402

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MOVED_CANDIDATE_CAP = 12  # parent-dir entries examined for file-moved discovery


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    import yaml
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"manifest load failure {manifest_path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("patches"), list):
        raise ToolError(f"{manifest_path}: not a patch manifest (no patches list)")
    return data


def _verify_sibling_at_pin(root: Path, manifest_hint: Path | None) -> Path:
    """Real mode: default manifest = ../xr-core at the DEPS-pinned rev."""
    deps = load_deps(root)
    pin = deps.get("xr_core_rev")
    if not SHA_RE.match(str(pin or "")):
        raise ToolError("DEPS xr_core_rev missing/not a 40-char SHA")
    sibling = (root.parent / "xr-core")
    if manifest_hint is not None:
        return manifest_hint
    manifest = sibling / "patches" / "manifest.yaml"
    if not manifest.exists():
        raise ToolError(
            f"manifest not found at {manifest} (xr-core rev {pin}? run build sync)")
    import subprocess
    head = subprocess.run(["git", "-C", str(sibling), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    if head.returncode != 0 or head.stdout.strip() != pin:
        raise ToolError(
            f"xr-core sibling HEAD {head.stdout.strip()!r} != DEPS pin {pin!r}; "
            "re-sync before rebasing (DEPS is the single source of truth)")
    return manifest


def resolve_to(source: GitilesFetchSource, to: str) -> str:
    if SHA_RE.match(to):
        return to
    for ref in (to if to.startswith("refs/") else f"refs/heads/{to}",
                f"refs/tags/{to}"):
        try:
            return source.ref_value(ref[len("refs/"):])
        except FetchError:
            continue
    raise ToolError(f"cannot resolve --to {to!r} as sha/branch/tag")


def _moved_targets(source, path: str, pin_text: str, to_rev: str) -> dict[str, str]:
    """file-moved discovery: identical pin content under a new name in the
    target-rev parent dir (capped, basename-token-preferring heuristic)."""
    import posixpath
    parent = posixpath.dirname(path)
    base = posixpath.basename(path)
    try:
        entries = source.dir_listing(to_rev, parent)
    except FetchError:
        return {}
    if base in entries:
        return {}  # target present; not a move
    stem = base.split(".")[0].split("_")[0].lower()
    scored = sorted((0 if stem and stem in e.lower() else 1, e) for e in entries)
    for _s, entry in scored[:MOVED_CANDIDATE_CAP]:
        cand = f"{parent}/{entry}"
        try:
            if hashlib.sha256(source.file_text(to_rev, cand).encode()).digest() == \
                    hashlib.sha256(pin_text.encode()).digest():
                return {path: cand}
        except FetchError:
            continue
    return {}


def run_rebase(*, to: str, manifest_path: Path, source, from_rev: str,
               source_label: str, work_dir: Path, dry_run: bool = False,
               root: Path | None = None, ledger_path: Path | None = None) -> dict:
    t0 = time.monotonic()
    root = root or repo_root()
    manifest = _load_manifest(manifest_path)
    to_resolved = resolve_to(source, to) if source_label == "real" else to

    range_log: list[dict[str, Any]] = []
    try:
        range_log = source.log(to_resolved, 20, start=from_rev)
    except FetchError:
        pass  # context is best-effort; classification is not

    patches_out: list[dict[str, Any]] = []
    for p in manifest["patches"]:
        pid = p.get("id")
        if not pid:
            raise ToolError(f"manifest patch without id: {p!r}")
        patch_dir = manifest_path.parent / p.get("dir", "")
        patch_texts = sorted((patch_dir / f"{pid}").glob("*.patch")) or \
            sorted(patch_dir.glob("*.patch"))
        if not patch_texts:
            raise ToolError(f"patch {pid}: no *.patch under {patch_dir}")
        patch_text = patch_texts[0].read_text(encoding="utf-8")

        pin_files: dict[str, str] = {}
        target_files: dict[str, str | None] = {}
        for f in p.get("files", []):
            pin_files[f] = source.file_text(from_rev, f)
            try:
                target_files[f] = source.file_text(to_resolved, f)
            except FetchError:
                target_files[f] = None

        moved: dict[str, str] = {}
        for f, tgt in target_files.items():
            if tgt is None:
                moved = {**moved, **_moved_targets(source, f, pin_files[f], to_resolved)}

        result: PatchResult = classify_patch(
            pid, p.get("owner", "?"), p.get("category", "?"),
            patch_text, pin_files, target_files, moved)
        patches_out.append({
            "id": result.id, "owner": result.owner, "category": result.category,
            "cls": result.cls, "source": source_label,
            "detail": result.detail,
            "files": [{"path": f.path, "cls": f.cls, "detail": f.detail,
                       "moved_to": f.moved_to} for f in result.files],
        })

    verdict = verdict_of([PatchResult(id=r["id"], owner=r["owner"],
                                      category=r["category"], cls=r["cls"],
                                      files=[]) for r in patches_out])
    report: dict[str, Any] = {
        "schema_version": 1, "tool": "xr-rebase", "source": source_label,
        "mode": "dry-run" if dry_run else "classified",
        "generated_at": _now_iso(),
        "from_rev": from_rev, "to_rev": to, "to_resolved": to_resolved,
        "wall_clock_seconds": round(time.monotonic() - t0, 3),
        "bytes_fetched": getattr(source, "bytes_fetched", 0),
        "verdict": verdict, "next_action": next_action(verdict),
        "patches": patches_out,
        "range_log": [{"commit": c.get("commit"), "subject": c.get("message", "").splitlines()[0] if c.get("message") else ""}
                      for c in range_log],
        "assumptions": {"status": "not-run (fixture mode)"}
        if source_label == "fixture" else {"status": "not-run"},
    }

    if ledger_path is not None and ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            for row in patches_out:
                row["ledger_state"] = ledger.get("applied", {}).get(row["id"])
        except (OSError, ValueError):
            pass  # ledger linkage is informational; never blocks classification

    fails = validate_rebase_report(report)
    if fails:
        raise ToolError("internal: report failed its own schema: " + "; ".join(fails))

    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "rebase-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if verdict != "GREEN":
        bundles = issues_mod.route(report, work_dir / "issues")
        report["issue_bundles"] = [str(b) for b in bundles]

    if verdict == "GREEN" and not dry_run and source_label == "real":
        report["prepared_branch"] = _prepare_deps_bump_branch(
            root, to_resolved, work_dir)

    return report


def _prepare_deps_bump_branch(root: Path, to_sha: str, work_dir: Path) -> str:
    """LOCAL-ONLY candidate DEPS-bump branch via plumbing (no checkout, no push)."""
    import subprocess
    deps = (root / "DEPS").read_text(encoding="utf-8")
    new_deps = re.sub(r'chromium_rev: "[0-9a-f]{40}"', f'chromium_rev: "{to_sha}"', deps)
    if new_deps == deps:
        raise ToolError("DEPS chromium_rev substitution failed (pattern drift)")
    short = to_sha[:12]
    branch = f"rebase/chromium-{short}"
    import tempfile
    with tempfile.TemporaryDirectory(prefix="xr-branch-") as td:
        env_idx = str(Path(td) / "index")
        def git(*args: str, input_: str | None = None, check: bool = True):
            import os
            env = {**os.environ, "GIT_INDEX_FILE": env_idx}
            r = subprocess.run(["git", "-C", str(root), *args], env=env,
                               input=input_, text=True, capture_output=True)
            if check and r.returncode != 0:
                raise ToolError(f"branch prep git {args[0]} failed: {r.stderr}")
            return r
        git("read-tree", "HEAD")
        blob = git("hash-object", "-w", "--stdin", input_=new_deps).stdout.strip()
        tree_of = subprocess.run(["git", "-C", str(root), "ls-tree", "HEAD", "DEPS"],
                                 capture_output=True, text=True, check=True).stdout.split()
        git("update-index", "--cacheinfo", f"{tree_of[0]},{blob},DEPS")
        tree = git("write-tree").stdout.strip()
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        msg = (f"upstream(rebase): candidate DEPS bump to {short} (prepared by xr-rebase)\n\n"
               "Classification GREEN at this rev (rebase-report.json). LOCAL branch\n"
               "only — never pushed by the bot; a human reviews and merges (L24).")
        commit = git("commit-tree", tree, "-p", head, input_=msg).stdout.strip()
        git("update-ref", f"refs/heads/{branch}", commit)
    return branch


def selftest() -> int:
    """The Plan's synthetic drill, offline: 5 patches, 3 sequential ranges."""
    import fixtures
    corpus = fixtures.build_corpus()
    source = fixtures.fixture_source_for(corpus)
    with __import__("tempfile").TemporaryDirectory(prefix="xr-selftest-") as td:
        manifest = fixtures.write_manifest_tree(Path(td), corpus)
        failures: list[str] = []
        for rev in (fixtures.REV_B, fixtures.REV_C, fixtures.REV_D):
            report = run_rebase(to=rev, manifest_path=manifest, source=source,
                                from_rev=fixtures.REV_A, source_label="fixture",
                                work_dir=Path(td) / "work", dry_run=True)
            expected = fixtures.expected_classes(rev)
            for row in report["patches"]:
                want = expected.get(row["id"], "clean")
                if row["cls"] != want:
                    failures.append(f"rev {rev[:8]} {row['id']}: got {row['cls']!r} want {want!r}")
            print(f"range -> {rev[:8]}: verdict={report['verdict']} "
                  f"({', '.join(r['id'].split('-', 2)[-1] + '=' + r['cls'].split('(')[0] for r in report['patches'])})")
        if failures:
            for f in failures:
                print(f"FAIL: {f}")
            return 1
        print("selftest: 5-patch classification drill PASS (clean/drift/moved/deleted/semantic)")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-rebase",
        description="Classify xr-core patch applicability at an upstream rev "
                    "(zero-clone; read-only; conflicts route to owner bundles).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rebase", help="run a classification pass")
    r.add_argument("--to", required=True, help="target ref (branch/tag) or 40-char sha")
    r.add_argument("--from", dest="from_rev", help="base rev (default: DEPS chromium_rev)")
    r.add_argument("--manifest", help="manifest path (default: ../xr-core at DEPS pin)")
    r.add_argument("--out", default="work/upstream-cache", help="work/output dir")
    r.add_argument("--dry-run", action="store_true",
                   help="report only — never cited as applied state, no branch prep")
    r.add_argument("--explain", action="store_true", help="one-glance verdict + next action")
    r.add_argument("--json", action="store_true", help="emit the report as JSON")
    sub.add_parser("selftest", help="offline 5-patch synthetic drill (Plan P3 Tests)")

    argv = sys.argv[1:]
    if argv and argv[0] == "selftest":
        return selftest()
    if not argv or (argv[0] != "rebase" and not argv[0].startswith("-")):
        raise SystemExit(parser.format_usage() + "error: expected 'rebase' or 'selftest'")
    if argv[0] != "rebase":
        sys.argv.insert(1, "rebase")
    args = parser.parse_args()
    if args.cmd == "selftest":
        return selftest()

    root = repo_root()
    manifest_path = _verify_sibling_at_pin(root, Path(args.manifest) if args.manifest else None)
    from_rev = args.from_rev or load_deps(root)["chromium_rev"]
    if not SHA_RE.match(from_rev):
        raise ToolError(f"--from/{from_rev!r} is not a 40-char SHA")
    source = GitilesFetchSource()
    ledger = Path(args.out) / ".xr" / "patch-apply.json"

    report = run_rebase(to=args.to, manifest_path=manifest_path, source=source,
                        from_rev=from_rev, source_label="real",
                        work_dir=Path(args.out), dry_run=args.dry_run,
                        root=root, ledger_path=ledger)

    if args.json:
        print(json.dumps(report, indent=2))
    if args.explain or not args.json:
        print(f"{report['verdict']}: {report['next_action']}")
        for row in report["patches"]:
            if row["cls"] != "clean":
                print(f"  {row['cls']:<24} {row['id']} (owner {row['owner']})")
        print(f"wall-clock {report['wall_clock_seconds']}s, "
              f"{report['bytes_fetched']} B fetched, mode={report['mode']}, "
              f"source={report['source']}")
    return 0 if report["verdict"] == "GREEN" else 1


if __name__ == "__main__":
    main_with_guard(lambda: main())
