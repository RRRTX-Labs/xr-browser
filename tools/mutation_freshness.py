#!/usr/bin/env python3
"""tools/mutation_freshness.py — the mutation-score freshness gate (P10-T0-c).

Law: a mutation score is a statement about specific bytes. If a core's
``<core>/core/**`` sources changed since the commit a recorded score was
produced at, the score is stale and the gate FAILS until a fresh transcript
lands. This is "phases are proven, not declared" applied to the provers —
it is exactly how P9's themes edits could have silently invalidated P8's
386/386 certification.

Inputs (all offline, deterministic):
  * ``docs/state/mutation-scores.json`` — the recorded scores (core ->
    xr_core_commit the full matrix ran at + transcript path + numbers);
  * ``DEPS`` ``xr_core_rev`` — the pin this tree is built against;
  * the sibling xr-core checkout — ``git diff --name-only
    <recorded>..<pin> -- <core>/core/`` decides freshness.

Failures (all FAIL, never warn):
  * a core whose core/** changed since its recorded commit (stale score);
  * a recorded commit that is not an ancestor of the pin (diverged record);
  * a missing transcript file or a missing record for a discovered core
    (every xr-core/<x>/core is discovered — a new core is auto-covered, the
    gate cannot be outgrown);
  * a survivors list whose entries lack a disposition.

Exit: 0 pass · 1 fail · 2 usage. Stdlib only. --as-of determinism.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEPS_RE = re.compile(r'xr_core_rev:\s*"([0-9a-f]{40})"')


def read_scores(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: {path}: unreadable scores ({exc})")


def current_pin(repo: Path) -> str:
    m = DEPS_RE.search((repo / "DEPS").read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("FAIL: DEPS has no xr_core_rev pin")
    return m.group(1)


def discover_cores(xr_core: Path) -> list[str]:
    found = sorted(d.parent.name for d in xr_core.glob("*/core")
                   if d.is_dir() and (d.parent / "tests").is_dir())
    if not found:
        raise SystemExit(f"FAIL: no cores discovered under {xr_core}")
    return found


def changed_core_files(xr_core: Path, old: str, new: str, core: str) -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(xr_core), "diff", "--name-only", f"{old}..{new}",
         "--", f"{core}/core/"],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(
            f"FAIL: git diff {old}..{new} failed for {core}: {r.stderr.strip()[:160]}")
    return [l for l in r.stdout.splitlines() if l.strip()]


def is_ancestor(xr_core: Path, old: str, new: str) -> bool:
    r = subprocess.run(
        ["git", "-C", str(xr_core), "merge-base", "--is-ancestor", old, new],
        capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="mutation-freshness",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--scores", default="docs/state/mutation-scores.json")
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    xr_core = Path(args.xr_core).resolve() if args.xr_core else repo.parent / "xr-core"
    if not xr_core.exists():
        print(f"FAIL: xr-core not found at {xr_core}")
        return 1

    scores = read_scores(repo / args.scores)
    pin = current_pin(repo)
    cores = discover_cores(xr_core)
    failures: list[str] = []
    fresh: list[str] = []

    for core in cores:
        rec = scores.get("cores", {}).get(core)
        if rec is None:
            failures.append(
                f"{core}: no mutation score recorded for a discovered core — "
                f"record one in {args.scores} (transcript from a full matrix at "
                f"the current pin)")
            continue
        rec_commit = rec.get("xr_core_commit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", rec_commit):
            failures.append(f"{core}: recorded xr_core_commit is not a 40-hex sha")
            continue
        if rec_commit == pin:
            if not (repo / rec.get("transcript", "")).exists():
                failures.append(f"{core}: transcript missing: {rec.get('transcript')}")
            else:
                fresh.append(core)
            continue
        if not is_ancestor(xr_core, rec_commit, pin):
            failures.append(
                f"{core}: recorded commit {rec_commit[:12]} is not an ancestor of "
                f"pin {pin[:12]} — the record diverged from this tree's history")
            continue
        changed = changed_core_files(xr_core, rec_commit, pin, core)
        if changed:
            failures.append(
                f"{core}: STALE mutation score — {len(changed)} core/** file(s) "
                f"changed since the recorded transcript ({rec_commit[:12]}): "
                f"{', '.join(changed[:4])}{' …' if len(changed) > 4 else ''}; "
                f"re-run the matrix for {core} and update {args.scores}")
        elif not (repo / rec.get("transcript", "")).exists():
            failures.append(f"{core}: transcript missing: {rec.get('transcript')}")
        else:
            fresh.append(core)

    # survivor dispositions must exist whenever anything survived
    for core, rec in scores.get("cores", {}).items():
        survivors = rec.get("survivors", [])
        for s in survivors:
            if not str(s.get("disposition", "")).strip():
                failures.append(f"{core}: survivor {s.get('id', '?')} has no disposition")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"FAIL: mutation-freshness ({len(failures)} stale/missing of {len(cores)} core(s))")
        return 1
    print(f"fresh cores: {', '.join(fresh) if fresh else '(none recorded)'}")
    print(f"PASS: mutation-freshness (pin {pin[:12]}, {len(cores)} core(s) fresh)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
