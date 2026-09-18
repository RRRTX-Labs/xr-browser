#!/usr/bin/env python3
"""tools/date_invariance_check.py — prove the gate's verdicts cannot move with
the calendar (P12-T0-a).

``tools/wall_clock_lint.py`` proves no gate tool READS the clock where it
should not. This tool proves the consequence: it re-runs every date-aware lane
in the push gate at two far-apart ``--as-of`` values and FAILs if any verdict
differs. A lint says "we did not see a clock"; this says "the answer was the
same a decade apart". Both are needed — the lint is the mechanism, this is the
property.

Default dates: 2026-01-01 and 2038-01-18 (the 2038 boundary is deliberate: it
is where a 32-bit time_t and any sloppy epoch arithmetic would disagree with a
date-only comparison, so a lane that secretly mixes the two reddens here).

Two tiers, because "date-invariant" is NOT one property (the finding that made
the first version of this tool redden on itself — see the P12 report):

  INVARIANT tier — the verdict MUST be identical at both dates (the push gate
  pins `--as-of`; the rendered bytes must not move): release-notes-bytes,
  release-notes-check, visual-diff-waived, visual-diff-expired.

  FRESHNESS tier — the verdict MUST differ in the expected direction (an expiry
  law that cannot expire is not a law). Making the gate date-invariant must NOT
  weaken it (brief failure condition 6): exception-ledger PASSes before the
  2027-06-01 expiry and FAILs after.

The ambient-clock half — displace the wall clock while ``--as-of`` stays pinned
— lives in tools/date_ambient_probe.py (touched-file size law). `faketime` is
an OPTIONAL helper tool (apt, docs/dependencies/helper-tools.yaml): without
``--require-ambient-probe`` the --as-of pair is the verdict and an absent tool
reports UNAVAILABLE (visible, never silent); with the flag a demand the host
cannot satisfy FAILS the lane (ADR-0047: a gate lane never hard-requires an
optional tool). Only the governance lane that apt-installs faketime passes it.

The zero-case law applies to both tiers: zero lanes executed is a FAIL.

Usage:  python3 tools/date_invariance_check.py [--repo .] [--json]
            [--dates 2026-01-01,2038-01-18] [--require-ambient-probe]
Exit: 0 pass · 1 drift (incl. an unsatisfiable strict probe) · 2 usage.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# The ambient-clock half + helper-tool discovery (split by the touched-file
# size law; P12-CLOSE T0-U1).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import date_ambient_probe as dap  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
DEFAULT_DATES = ("2026-01-01", "2038-01-18")
FIXTURE = "tools/fixtures/release-notes-train-152.json"
# The value run_checks.sh pins. The ambient probe holds this constant while
# moving the wall clock, which is exactly the gate's own configuration.
GATE_PINNED_AS_OF = "2026-09-14"


def _run(repo: Path, argv: list[str], *,
         env_date: str | None = None) -> tuple[int, str]:
    import os
    env = dict(os.environ)
    lib = dap.faketime_lib() if env_date else None
    if env_date and lib:
        env["LD_PRELOAD"] = lib
        env["FAKETIME"] = f"{env_date} 12:00:00"
        env["FAKETIME_NO_CACHE"] = "1"
    r = subprocess.run([sys.executable] + argv, cwd=repo, env=env,
                       capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def _verdict_token(text: str) -> str:
    """The verdict word, not the prose: PASS/FAIL/STALE-FAIL/verdict line."""
    for line in text.splitlines():
        for tok in ("STALE-FAIL", "PASS", "FAIL"):
            if line.startswith(tok):
                return tok
        for tok in ("WAIVED", "DIFFERENT", "IDENTICAL"):
            if line.startswith(tok + ":"):
                return tok
    return "NO-VERDICT"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lane_release_notes(repo: Path, as_of: str, td: Path, *,
                       env_date: str | None = None) -> dict:
    tag = as_of if env_date is None else f"{as_of}@{env_date}"
    out = td / f"train-152.{tag}.md"
    rc, txt = _run(repo, ["tools/release_notes.py", "--train", "152",
                          "--fixture", FIXTURE, "--as-of", as_of,
                          "--out", str(out)], env_date=env_date)
    rc2, txt2 = _run(repo, ["tools/release_notes.py", "--train", "152",
                            "--fixture", FIXTURE, "--as-of", as_of,
                            "--out", "release/notes/train-152.md", "--check"],
                     env_date=env_date)
    return {"render_rc": rc, "bytes_sha256": _sha(out),
            "check_rc": rc2, "check_verdict": _verdict_token(txt2)}


def lane_exception_ledger(repo: Path, as_of: str, td: Path, *,
                          env_date: str | None = None) -> dict:
    rc, txt = _run(repo, ["tools/exception_ledger_check.py",
                          "--as-of-date", as_of], env_date=env_date)
    tail = [ln for ln in txt.splitlines() if ln.startswith(("PASS", "FAIL"))]
    return {"rc": rc, "verdict": _verdict_token(txt),
            "summary": tail[-1] if tail else "NO-SUMMARY"}


def lane_visual_diff(repo: Path, as_of: str, td: Path, *, expiry: str,
                     tag: str, env_date: str | None = None) -> dict:
    """A waiver whose expiry is on one side of BOTH probe dates: the verdict
    must be identical at both, which is what date-invariance means here."""
    sys.path.insert(0, str(repo))
    from build.qa.visual import engine, pngcodec
    flat = bytearray()
    for _ in range(16 * 16):
        flat += bytes((200, 30, 30, 255))
    a = pngcodec.Image(16, 16, bytearray(flat))
    tweaked = bytearray(flat)
    tweaked[0] = 201  # 1-delta on R: a real difference
    b = pngcodec.Image(16, 16, tweaked)
    ref = td / f"{tag}-ref.png"
    cand = td / f"{tag}-cand.png"
    ref.write_bytes(pngcodec.encode(a))
    cand.write_bytes(pngcodec.encode(b))
    waivers = td / f"{tag}-waivers.yaml"
    waivers.write_text(
        "schema_version: 1\nwaivers:\n"
        f"  - snapshot: {tag}\n"
        f"    reference_hash: \"{engine.sha256_png(ref.read_bytes())}\"\n"
        f"    reason: date-invariance probe\n    owner: p12\n"
        f"    expiry: \"{expiry}\"\n", encoding="utf-8")
    rc, txt = _run(repo, ["tools/visual_diff.py", "--ref", str(ref),
                          "--cand", str(cand), "--waivers", str(waivers),
                          "--as-of", as_of], env_date=env_date)
    return {"rc": rc, "verdict": _verdict_token(txt)}


def run_lanes(repo: Path, as_of: str, td: Path, *,
              env_date: str | None = None) -> dict:
    """env_date, when set, runs the lanes under a displaced AMBIENT calendar
    (a real `date` binary via faketime) while `--as-of` stays pinned — the
    property the push gate actually needs. Probing --as-of alone cannot see a
    tool that reads today() directly, because --as-of never changes what
    today() returns inside one run."""
    return {
        "release-notes-bytes": lane_release_notes(repo, as_of, td,
                                                  env_date=env_date),
        "exception-ledger": lane_exception_ledger(repo, as_of, td,
                                                  env_date=env_date),
        "visual-diff-waived": lane_visual_diff(repo, as_of, td,
                                               expiry="2999-01-01",
                                               tag="unexpired",
                                               env_date=env_date),
        "visual-diff-expired": lane_visual_diff(repo, as_of, td,
                                                expiry="2000-01-01",
                                                tag="expired",
                                                env_date=env_date),
    }


# Which lane belongs to which tier, as DATA. `freshness_boundary` is the date
# the ledger's own expiry column crosses (docs/shield §1.13: 2027-06-01).
INVARIANT_LANES = ("release-notes-bytes", "visual-diff-waived",
                   "visual-diff-expired")
FRESHNESS_LANES = {"exception-ledger": "2027-06-01"}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="date_invariance_check",
                                description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=".")
    p.add_argument("--dates", default=",".join(DEFAULT_DATES))
    p.add_argument("--json", action="store_true")
    p.add_argument("--require-ambient-probe", action="store_true",
                   help="demand the ambient-clock half: on a host without "
                        "the `faketime` helper tool the run FAILS rather "
                        "than degrading to the --as-of half only. The "
                        "default run_checks.sh path does NOT set this; only "
                        "the governance lane that apt-installs faketime "
                        "does (ADR-0047).")
    a = p.parse_args(argv)
    repo = Path(a.repo).resolve()
    dates = [d.strip() for d in a.dates.split(",") if d.strip()]
    if len(dates) < 2:
        print("usage: --dates needs at least two far-apart ISO dates")
        return EXIT_USAGE
    for d in dates:
        try:
            import datetime
            datetime.date.fromisoformat(d)
        except ValueError:
            print(f"usage: {d!r} is not a YYYY-MM-DD date")
            return EXIT_USAGE

    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        for d in dates:
            results[d] = run_lanes(repo, d, td)
        # Ambient-clock probe: --as-of PINNED at the gate's own value while
        # the wall clock moves; identical verdicts required. Discovered and
        # run by the split module (helper-tool discovery + probe self-check
        # live there).
        ambient = None
        ambient_probe_error = ""
        if dap.have_faketime() and dap.faketime_lib():
            base = run_lanes(repo, GATE_PINNED_AS_OF, td)
            extra, err = dap.run_ambient_tier(repo, GATE_PINNED_AS_OF, td,
                                              base, run_lanes)
            results.update(extra)
            if err:
                ambient, ambient_probe_error = "probe-error", err
            else:
                ambient = "faketime"

    lanes = sorted(results[dates[0]])
    ambient_lanes = sorted(k for k in results if k.startswith("ambient:"))
    if not lanes:
        print("FAIL: date_invariance_check executed 0 lane(s) — a runner "
              "that runs nothing certifies nothing")
        return EXIT_FAIL
    ambient_drift: list[str] = []
    for k in ambient_lanes:
        lane, _, shift = k.partition("@")
        base_key = f"{lane}@pinned"
        if json.dumps(results[k], sort_keys=True) != \
                json.dumps(results[base_key], sort_keys=True):
            ambient_drift.append(
                f"{lane}: verdict changed when the AMBIENT clock moved to "
                f"{shift} with --as-of pinned at {GATE_PINNED_AS_OF} — "
                f"this tool reads the wall clock: {results[k]} != "
                f"{results[base_key]}")

    unknown = [ln for ln in lanes
               if ln not in INVARIANT_LANES and ln not in FRESHNESS_LANES]
    if unknown:
        print(f"FAIL: date_invariance_check — lane(s) {unknown} are in no "
              f"tier; classify them as data before shipping")
        return EXIT_FAIL

    early, late = min(dates), max(dates)
    drift: list[str] = []

    # Tier 1: identical at every date.
    for lane in INVARIANT_LANES:
        blobs = {d: json.dumps(results[d][lane], sort_keys=True)
                 for d in dates}
        if len(set(blobs.values())) != 1:
            drift.append(f"INVARIANT {lane}: verdict differs across {dates}: "
                         + " | ".join(f"{d}={blobs[d]}" for d in dates))

    # Tier 2: the expiry law must still bite (a freshness law that cannot
    # expire was silently weakened — brief failure condition 6).
    for lane, boundary in sorted(FRESHNESS_LANES.items()):
        if not (early < boundary <= late):
            drift.append(f"FRESHNESS {lane}: probe dates {early}..{late} do "
                         f"not straddle the {boundary} expiry boundary, so "
                         f"this run cannot prove the law still bites")
            continue
        before = results[early][lane]["verdict"]
        after = results[late][lane]["verdict"]
        if not (before == "PASS" and after == "FAIL"):
            drift.append(f"FRESHNESS {lane}: expiry law does not bite — "
                         f"verdict was {before} at {early} and {after} at "
                         f"{late} across the {boundary} boundary (expected "
                         f"PASS then FAIL)")

    drift += ambient_drift
    ambient_note = ""
    if ambient is None:
        if a.require_ambient_probe:
            # T0-U1 (ADR-0047): the strict lane demanded a probe the host
            # cannot satisfy — certifying less than it claims is not an
            # option. Tool text is build/skip_policy.py's (reuse, don't
            # invent); the inline fallback keeps the fixture honest.
            abs_reason = dap.skip_policy_absent_reason(repo)
            hint = "install hint: apt-get install -y faketime"
            if abs_reason is None:
                drift.append("ambient-clock probe UNAVAILABLE but "
                             "--require-ambient-probe was set — the "
                             "wall-clock half of this law is unproven, so a "
                             f"run that demanded it certifies less than it "
                             f"claims ({hint})")
            else:
                drift.append(f"{abs_reason} — but --require-ambient-probe "
                             f"was set, so a run that demanded the "
                             f"ambient-clock half certifies less than it "
                             f"claims ({hint})")
        else:
            ambient_note = ("ambient-clock probe UNAVAILABLE (faketime "
                            "absent) — the --as-of half is proven, the "
                            "wall-clock half is NOT")
    elif ambient == "faketime":
        ambient_note = (f"{len(ambient_lanes)} ambient-clock probe(s) via "
                        f"faketime")
    elif ambient == "probe-error":
        drift.append(f"ambient-clock probe DID NOT RUN: {ambient_probe_error}")
    if a.json:
        print(json.dumps({"tool": "date_invariance_check", "dates": dates,
                          "lanes": lanes, "drift": drift,
                          "ambient_probe": ambient or "unavailable"},
                         sort_keys=True, indent=2))
    if drift:
        print(f"FAIL: date_invariance_check — {len(drift)} problem(s):")
        for d in drift:
            print(f"  {d}")
        return EXIT_FAIL
    print(f"PASS: date_invariance_check ({len(INVARIANT_LANES)} invariant "
          f"lane(s) identical across {len(dates)} dates "
          f"[{' .. '.join(dates)}]; {len(FRESHNESS_LANES)} freshness lane(s) "
          f"still bite across their expiry boundary; {ambient_note} — the "
          f"push gate is date-invariant and no freshness law was weakened)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
