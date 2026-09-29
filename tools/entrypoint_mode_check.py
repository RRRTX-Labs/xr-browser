#!/usr/bin/env python3
"""tools/entrypoint_mode_check.py — the index-mode law for entry points (P13 P0-A).

Why this exists (the incident, verbatim from the tree)
------------------------------------------------------
Every hosted `governance` run since P12-CLOSE died at the "Governance checks"
step with `Process completed with exit code 126` — the shell's "cannot execute"
— because `tools/run_checks.sh` and `tools/run_negatives.sh` were tracked
`100644` in the INDEX while `governance.yml` invoked both *directly*
(`tools/run_checks.sh "$CHECK_RANGE"`). `bash tools/run_checks.sh` cannot see
this: bash is the executable, so the file's mode is not load-bearing. Three
consecutive "fix the CI" commits chased real-but-different causes and never
turned the lane green because the actual cause was a mode bit.

`git show 5e3d1d4 --raw` is the whole story: that commit flips exactly those
two paths `100755 -> 100644`, and `tools/run_checks.sh`'s *content* is
byte-identical there (mode-only diff) — a write-new-then-replace rewrite. The
class, not the instance, is what this tool makes impossible: two laws.

  Law 1 (entry-point mode): every `.github/workflows/*.yml` `run:` block is
  parsed; for every command whose FIRST token is a repo path executed DIRECTLY,
  the git INDEX mode must be `100755`. Exempt — and this exemption is stated in
  the output, not silent — are interpreted invocations (`bash <path>`,
  `python3 <path>`, `node <path>`): there the interpreter is the executable, so
  the file's mode is not load-bearing. The workflow-invoked scripts are 100755
  *by law* (CODEBASE REQUIREMENTS), which is why only the direct form is a
  violation.

  Law 2 (mode drift, `--range`): no commit in a pushed range may change a
  tracked file's index mode from `100755` to `100644`. This is the commit-level
  version of the same law: `5e3d1d4` would redden here at push time, with the
  commit and the path named, instead of surfacing as a runner exit code a week
  later.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage · 77 SKIP (no git / no workflows).
`--json` for machine reading; `--self-test` proves both laws can fail, on a
throwaway repo in a temp dir (never in this tree).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77

# The `run:`-block parser lives in tools/wfrun.py (P13-P0-A size-law split:
# this file was 443 lines with it inline). Re-exported here so callers
# and tests keep one import surface.
from wfrun import (  # noqa: F401  (re-export)
    INTERPRETERS, PREAMBLE, SHELL_KEYWORDS, PATH_RE, RUN_RE,
    _mask_expressions, extract_run_blocks, split_commands, classify_command,
)


# ------------------------------------------------------------------ inspection

def _git(repo: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return p.returncode, p.stdout


def index_modes(repo: Path) -> dict[str, str] | None:
    """path -> index mode ('100755'/'100644'/'120000'), or None if no git."""
    if not shutil.which("git"):
        return None
    rc, out = _git(repo, "ls-files", "-s")
    if rc != 0:
        return None
    modes: dict[str, str] = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        bits = meta.split()
        if len(bits) == 3:
            modes[path] = bits[0]
    return modes


def check_entrypoints(repo: Path, modes: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(failures, notes, exempt-descriptions)."""
    wf_dir = repo / ".github" / "workflows"
    files = sorted(wf_dir.glob("*.yml"))
    tracked = set(modes)
    failures: list[str] = []
    exempt: list[str] = []
    notes: list[str] = []
    direct_seen = 0
    for wf in files:
        rel = wf.relative_to(repo).as_posix()
        text = wf.read_text(encoding="utf-8")
        for line_no, block in extract_run_blocks(text):
            for cmd in split_commands(block):
                kind, path = classify_command(cmd, tracked)
                if kind == "interpreted" and path:
                    exempt.append(f"{rel}:{line_no} {cmd.split()[0]} {path}")
                elif kind == "direct":
                    direct_seen += 1
                    mode = modes.get(path)
                    if mode is None:
                        failures.append(
                            f"{rel}:{line_no}: `{path}` is executed directly but is "
                            "not tracked in the index — a fresh clone cannot run it")
                    elif mode != "100755":
                        failures.append(
                            f"{rel}:{line_no}: `{path}` is executed DIRECTLY but its "
                            f"index mode is {mode}, not 100755 — on a runner this is "
                            "exit code 126 ('Process completed with exit code 126'), "
                            "the failure mode that kept the governance lane red for "
                            f"three commits. Fix: git update-index --chmod=+x {path}\n"
                            f"  (class precedent: 5e3d1d4 flipped {path if path.endswith('.sh') else 'tools/*.sh'} "
                            "to 100644 with a write-new-then-replace rewrite)")
    # One finding per (file, path): a step that invokes the same entry point
    # twice (the `if [ -n "$RANGE" ] … else … fi` shape) is one defect.
    seen: set[str] = set()
    unique: list[str] = []
    for f in failures:
        key = f.split(": `", 1)[-1].split("`", 1)[0] + f.splitlines()[0]
        if key not in seen:
            seen.add(key)
            unique.append(f)
    failures = unique

    notes.append(
        f"workflow files: {len(files)}; directly executed repo paths: {direct_seen}; "
        f"interpreted invocations EXEMPT: {len(exempt)} (`bash`/`python3 <path>` — the "
        "interpreter is the executable, so the file's mode is not load-bearing)")
    return failures, notes, sorted(set(exempt))


def check_mode_drift(repo: Path, rev_range: str) -> list[str]:
    """Law 2: no commit in <range> may drop the exec bit (100755 -> 100644)."""
    rc, out = _git(repo, "log", "--no-renames", "-m", "--raw",
                   "--format=CMT %x00%H %s", rev_range, "--")
    if rc != 0:
        return [f"`git log {rev_range}` failed — the mode-drift law cannot be "
                "evaluated (failing closed rather than skipping silently)"]
    failures: list[str] = []
    commit, subject = "", ""
    for line in out.splitlines():
        if line.startswith("CMT "):
            commit, _, subject = line[4:].partition(" ")
            commit = commit.strip("\x00").split()[0] if commit else ""
            subject = subject.replace("\x00", " ").strip()
            continue
        if not line.startswith(":"):
            continue
        meta, _, path = line[1:].partition("\t")
        bits = meta.split()
        if len(bits) >= 4 and bits[0] == "100755" and bits[1] == "100644":
            failures.append(
                f"{commit[:12]} ({subject}): {path} lost its executable bit "
                "(100755 -> 100644) in this range — the 5e3d1d4 class. Either "
                "restore the bit (`git update-index --chmod=+x <path>`) or, if "
                "the file is genuinely not an entry point any more, say so in "
                "the commit message and add it to the tool's waiver list")
    return failures


# ---------------------------------------------------------------------- output

def _self_test() -> int:
    """Both laws must be able to fail, on a throwaway repo. Nothing here writes
    into the real tree."""
    tmp = Path(tempfile.mkdtemp(prefix="xr-entrymode-"))
    try:
        def g(*a: str, check: bool = True) -> subprocess.CompletedProcess:
            p = subprocess.run(["git", "-c", "user.email=t@x", "-c", "user.name=t", *a],
                               cwd=tmp, capture_output=True, text=True)
            if check and p.returncode != 0:
                raise SystemExit(f"self-test git {a} failed: {p.stderr}")
            return p

        g("init", "-q")
        (tmp / ".github" / "workflows").mkdir(parents=True)
        (tmp / "tools").mkdir()
        (tmp / ".github" / "workflows" / "w.yml").write_text(
            "name: w\non: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - name: gate\n        run: |\n"
            "          ./tools/planted.sh \"$R\"\n"
            "          bash tools/planted.sh\n"
            "          python3 tools/planted.py --json\n"
            "          python3 - <<'PY'\n"
            "          print('inline heredoc, not a repo path')\n"
            "          PY\n",
            encoding="utf-8")
        (tmp / "tools" / "planted.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (tmp / "tools" / "planted.py").write_text("print('x')\n", encoding="utf-8")
        (tmp / "tools" / "planted.sh").chmod(0o644)          # the planted defect
        g("add", "-A")
        g("commit", "-qm", "self-test: planted 644 entry point")

        modes = index_modes(tmp)
        assert modes is not None, "no index readable in the self-test repo"
        fails, notes, exempt = check_entrypoints(tmp, modes)
        assert any("planted.sh" in f and "100644" in f for f in fails), \
            f"Law 1 did not fire on a 644 direct-exec entry point: {fails}"
        assert not any("planted.py" in f for f in fails), \
            "Law 1 fired on an interpreted invocation — the exemption is broken"
        assert any("planted.py" in e for e in exempt), \
            "the exempt list did not record the interpreted invocation"
        print("ok: self-test Law 1 (644 direct-exec entry point reddens; "
              "`bash`/`python3 <path>` is exempt and listed)")

        g("update-index", "--chmod=+x", "tools/planted.sh")
        g("commit", "-qm", "self-test: correct the mode")
        fails, _, _ = check_entrypoints(tmp, index_modes(tmp))
        assert not fails, f"Law 1 stayed red after the mode was corrected: {fails}"
        print("ok: self-test Law 1 positive control (corrected mode is clean)")

        g("update-index", "--chmod=-x", "tools/planted.sh")
        g("commit", "-qm", "self-test: drop the bit again (the 5e3d1d4 shape)")
        drift = check_mode_drift(tmp, "HEAD~1..HEAD")
        assert any("planted.sh" in d and "100755 -> 100644" in d for d in drift), \
            f"Law 2 did not fire on a dropped exec bit: {drift}"
        assert not check_mode_drift(tmp, "HEAD..HEAD"), \
            "Law 2 fired on an empty range (a false positive)"
        print("ok: self-test Law 2 (a dropped exec bit reddens with commit + path; "
              "an empty range stays clean)")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="repository root")
    ap.add_argument("--range", dest="rev_range", default="",
                    help="git range for the mode-drift law (e.g. base..HEAD)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    repo = Path(args.repo).resolve()
    modes = index_modes(repo)
    if modes is None:
        print("SKIP (entry-point mode check): no readable git index at "
              f"{repo} — needed for: the index-mode law (a filesystem mode is "
              "not what a runner checks out)")
        return EXIT_SKIP
    if not (repo / ".github" / "workflows").is_dir():
        print(f"SKIP (entry-point mode check): no .github/workflows at {repo}")
        return EXIT_SKIP

    failures, notes, exempt = check_entrypoints(repo, modes)
    drift: list[str] = []
    if args.rev_range:
        drift = check_mode_drift(repo, args.rev_range)

    doc = {
        "tool": "entrypoint_mode_check",
        "repo": str(repo),
        "range": args.rev_range or None,
        "law_1_entry_points": {"status": "PASS" if not failures else "FAIL",
                               "failures": failures},
        "law_2_mode_drift": {"status": "PASS" if not drift else "FAIL",
                             "failures": drift},
        "notes": notes,
        "exempt_interpreted": exempt,
    }
    if args.json:
        print(json.dumps(doc, indent=1, sort_keys=True))
    elif not args.quiet:
        for n in notes:
            print(n)
        for e in exempt:
            print(f"  exempt (interpreted): {e}")
        for f in failures:
            print(f"FAIL: {f}")
        for d in drift:
            print(f"FAIL (mode drift): {d}")
        if not failures and not drift:
            print("PASS: every workflow-invoked direct entry point is 100755 in "
                  "the index and no commit in range dropped an exec bit")
    return EXIT_PASS if not (failures or drift) else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
