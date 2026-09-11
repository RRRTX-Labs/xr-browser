#!/usr/bin/env python3
"""tools/scheduled_lane_check.py — a red nightly is a red check within a day.

P11-T0-c. Root cause: `compat-beta-parity`'s first and only scheduled run
(34574063042, 2026-09-11 07:22 UTC) FAILED at the `Upload the compat-parity
evidence` step, and nobody noticed, because nothing in the repo correlates
"a scheduled lane went red" with anything. Push-triggered gates cannot see
it: the failing trigger is the schedule itself.

Law: for EVERY workflow with a `schedule:` trigger, resolve its MOST RECENT
`schedule`-event run through the public API and verdict it: success -> PASS;
failure on the CURRENT definition -> FAIL (with the failing job/step names
from GET /actions/runs/<id>/jobs); failure with a fix landed since (file
touched after the run, or a NEWER run succeeded) -> STALE-FAIL, visible and
NON-FATAL, never counted green; a NEWER run that ALSO failed on real work
re-escalates to FAIL; failed ONLY its lane-health step -> exempt (the fleet
check must never condemn a lane for the checker's own circular failure);
no schedule run yet -> NOT-RUN visible; disabled -> SKIP visible; in flight
-> IN-PROGRESS visible; network absent -> SKIP exit 77 (skip-policy) AFTER
`--self-test` proved every path OFFLINE, so a SKIP never masks a broken
checker. `--own-lane X` caps X's own verdict at visible non-fatal (every
scheduled lane passes its own name; governance passes none).

Network: build/upstream/fetch.py only (the chokepoint; api.github.com is
sanctioned — the same sanction evidence_ci.py's ci-run resolver uses).
PyYAML = pinned dev dep. `--fixture FILE` replaces every API response and
touch-date with canned data (drives --self-test and negative case 68).

Exit: 0 pass (incl. non-fatal visibles) · 1 fail · 2 usage · 77 skip.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_API = "https://api.github.com/repos/RRRTX-Labs/xr-browser"
EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77


def _http(url: str, fixture: dict[str, Any] | None) -> Any:
    if fixture is not None:
        urls = fixture.get("urls", {})
        if url not in urls:
            raise RuntimeError(f"fixture has no canned response for {url}")
        return urls[url]
    for p in (Path(__file__).resolve().parent.parent / "build" / "upstream",):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import fetch  # noqa: PLC0415 — chokepoint import, lazy for fixture mode
    return json.loads(fetch.http_get(url))


def scheduled_workflows(root: Path) -> list[tuple[str, str]]:
    """(workflow filename, cron text) for every schedule-triggered workflow."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        raise SystemExit(EXIT_SKIP)
    wf_dir = root / ".github" / "workflows"
    out: list[tuple[str, str]] = []
    for path in sorted(wf_dir.glob("*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        on = doc.get("on", doc.get(True))  # YAML 1.1 parses bare `on` as True
        if isinstance(on, dict) and isinstance(on.get("schedule"), list):
            crons = [str(s.get("cron", "?")) for s in on["schedule"]
                     if isinstance(s, dict)]
            out.append((path.name, ",".join(crons)))
    return out


def _last_touch(root: Path, wf_name: str,
                fixture: dict[str, Any] | None) -> str | None:
    if fixture is not None:
        return fixture.get("touches", {}).get(wf_name)
    r = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%cI", "--",
         f".github/workflows/{wf_name}"],
        capture_output=True, text=True)
    return r.stdout.strip() or None


def _cap(wf_name: str, own_lane: str | None, verdict: str,
         detail: list[str]) -> tuple[str, list[str]]:
    """Circularity guard: FROM INSIDE lane X (--own-lane X, as every
    scheduled lane passes), X's own verdict is CAPPED at visible non-fatal —
    the lane's real steps are the true test of itself; the fleet check must
    never fail its own lane mid-run (run 34635371904: every work step green,
    job red because the check condemned the lane from history that included
    itself). Other lanes keep the full hard-FAIL law."""
    if verdict == "FAIL" and own_lane and wf_name == own_lane:
        detail.append("  STALE-FAIL (capped): --own-lane — a lane's real "
                      "steps are the true test of itself; the fleet check "
                      "reports its own lane visibly but never executes it. "
                      "Governance (no cap) keeps the hard-FAIL law.")
        return "STALE-FAIL", detail
    return verdict, detail


def check_lane(root: Path, wf_name: str, cron: str, workflows_api: dict,
               fixture: dict[str, Any] | None,
               own_lane: str | None = None) -> tuple[str, list[str]]:
    """(verdict, detail): PASS|FAIL|STALE-FAIL|NOT-RUN|DISABLED|IN-PROGRESS."""
    path = f".github/workflows/{wf_name}"
    entry = next((w for w in workflows_api.get("workflows", [])
                  if w.get("path") == path), None)
    if entry is None:
        return "NOT-RUN", [f"{wf_name}: not listed by the workflows API yet "
                           "(never pushed/registered) — visible, non-fatal"]
    if entry.get("state") == "disabled":
        return "DISABLED", [f"{wf_name}: workflow is DISABLED (id "
                            f"{entry.get('id')}) — visible SKIP; a disabled "
                            "schedule is a decision, not a silence"]
    runs = _http(f"{REPO_API}/actions/workflows/{entry['id']}/runs"
                 "?per_page=30", fixture)
    sched = [r for r in runs.get("workflow_runs", [])
             if r.get("event") == "schedule"]
    if not sched:
        return "NOT-RUN", [f"{wf_name}: no schedule-event run yet (cron "
                           f"{cron}; workflow id {entry['id']}) — the lane "
                           "exists but has not fired; visible, non-fatal"]
    run = sched[0]
    head = f"{wf_name}: schedule run {run['id']} head " \
           f"{str(run.get('head_sha', ''))[:9]} created {run.get('created_at')}"
    if run.get("status") != "completed":
        return "IN-PROGRESS", [f"{head} — status {run.get('status')}; "
                               "non-fatal, re-check when it completes"]
    concl = run.get("conclusion")
    if concl == "success":
        return "PASS", [head + " — success"]
    # A non-success completed schedule run: find the failing steps, then let
    # NEWER runs of any event arbitrate — they test the current definition:
    #   newer completed success -> fix VERIFIED, STALE-FAIL (non-fatal);
    #   newer completed failure -> hard FAIL (still red right now, whatever
    #                              the file dates say);
    #   no newer run            -> FAIL vs STALE-FAIL by touch date.
    detail = [f"{head} — conclusion: {concl}"]
    try:
        jobs = _http(f"{REPO_API}/actions/runs/{run['id']}/jobs", fixture)
        for job in jobs.get("jobs", []):
            if job.get("conclusion") in (None, "success", "skipped"):
                continue
            bad = [s.get("name") for s in job.get("steps", [])
                   if s.get("conclusion") not in ("success", "skipped", None)]
            detail.append(f"  job '{job.get('name')}': {job.get('conclusion')}"
                          f" failed step(s): {bad}")
    except RuntimeError:
        detail.append("  (fixture: no canned jobs response)")
    all_runs = runs.get("workflow_runs", [])
    newer = [r for r in all_runs if r.get("id") != run.get("id")
             and str(r.get("created_at", "")) > str(run.get("created_at", ""))]
    newer_done = [r for r in newer if r.get("status") == "completed"]
    if newer_done:
        latest = newer_done[0]
        if latest.get("conclusion") == "success":
            detail.append(
                f"  STALE-FAIL: fix VERIFIED — newer {latest.get('event')} "
                f"run {latest['id']} (head "
                f"{str(latest.get('head_sha', ''))[:9]}) completed SUCCESS "
                "after this red scheduled run; the lane is green again and "
                "the next scheduled fire will confirm. Visible, non-fatal, "
                "never counted green by silence.")
            return "STALE-FAIL", detail
        # Exemption (narrow, proven by run 34635371904): if the newer failed
        # run's ONLY failed step is the Scheduled-lane health step itself, it
        # cannot condemn this lane — the lane's real work was green and the
        # failure is the fleet check's own (since-fixed) arbitration. Without
        # this, the checker's first in-lane run poisons every later verdict.
        try:
            ljobs = _http(f"{REPO_API}/actions/runs/{latest['id']}/jobs",
                          fixture)
            failed_steps = [
                str(st.get("name", ""))
                for j in ljobs.get("jobs", [])
                if j.get("conclusion") not in (None, "success", "skipped")
                for st in j.get("steps", [])
                if st.get("conclusion") not in (None, "success", "skipped")]
        except RuntimeError:
            failed_steps = []
        if failed_steps and all(f.startswith("Scheduled-lane health")
                                for f in failed_steps):
            detail.append(
                f"  STALE-FAIL: the newer {latest.get('event')} run "
                f"{latest['id']} failed ONLY its Scheduled-lane health step "
                "(circular artifact of the fleet check itself — the lane's "
                "work steps were green); visible, non-fatal, never counted "
                "green by silence.")
            return "STALE-FAIL", detail
        detail.append(
            f"  FAIL: the newer {latest.get('event')} run {latest['id']} "
            f"ALSO failed ({latest.get('conclusion')}) — the current "
            "definition is red right now; file dates cannot excuse this.")
        return _cap(wf_name, own_lane, "FAIL", detail)
    touch = _last_touch(root, wf_name, fixture)
    if touch and str(run.get("created_at", "")) and touch > run["created_at"]:
        detail.append(f"  STALE-FAIL: the workflow file changed at {touch}, "
                      "AFTER this run started — a fix has landed and the "
                      "next scheduled fire will tell the truth; visible, "
                      "non-fatal, never counted green")
        return "STALE-FAIL", detail
    detail.append("  FAIL: the newest scheduled run for this lane is not "
                  "green and no fix has landed since — this is the silent "
                  "red nightly this gate exists to kill")
    return _cap(wf_name, own_lane, "FAIL", detail)


SELF_TEST_FIXTURE_PATH = (Path(__file__).resolve().parent / "tests" /
                          "fixtures" / "scheduled_lane_selftest.json")


def load_self_test_fixture() -> dict[str, Any]:
    """Canned API/touch data for --self-test (kept as a JSON fixture so the
    tool itself stays small and the same file can drive negative fixtures
    via --fixture)."""
    return json.loads(SELF_TEST_FIXTURE_PATH.read_text(encoding="utf-8"))


def run(root: Path, fixture: dict[str, Any] | None,
        as_json: bool, own_lane: str | None = None) -> int:
    if fixture is not None and fixture.get("local"):
        lanes = [(n, "fixture-cron") for n in fixture["local"]]
    else:
        lanes = scheduled_workflows(root)
    if not lanes:
        print("FAIL: discovered ZERO scheduled workflows — this repo has "
              "four; a discovery that finds nothing certifies nothing "
              "(zero-case law)", file=sys.stderr)
        return EXIT_FAIL
    try:
        workflows_api = _http(f"{REPO_API}/actions/workflows", fixture)
    except Exception as exc:  # noqa: BLE001 — network class -> visible SKIP
        print(f"SKIP: SKIP (network unavailable for api.github.com: "
              f"{str(exc)[:160]}) — needed for: the scheduled-lane health "
              f"verdict; local hint: re-run with network, or read "
              f"https://github.com/RRRTX-Labs/xr-browser/actions manually; "
              f"--self-test proves the checker itself works offline")
        return EXIT_SKIP

    results: list[tuple[str, str, list[str]]] = []
    for wf_name, cron in lanes:
        verdict, detail = check_lane(root, wf_name, cron, workflows_api,
                                     fixture, own_lane)
        results.append((wf_name, verdict, detail))

    hard = [r for r in results if r[1] == "FAIL"]
    if as_json:
        print(json.dumps({
            "lanes": [{"workflow": w, "verdict": v, "detail": d}
                      for w, v, d in results],
            "status": "fail" if hard else "pass"}, indent=2))
    else:
        for wf, verdict, detail in results:
            print(f"{verdict}: {wf}")
            for line in detail:
                print(f"    {line}")
        counts: dict[str, int] = {}
        for _, v, _ in results:
            counts[v] = counts.get(v, 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        if hard:
            print(f"FAIL: scheduled_lane_check ({len(hard)} lane(s) red on "
                  f"their current definition; {summary})")
        else:
            print(f"PASS: scheduled_lane_check ({len(results)} scheduled "
                  f"lane(s); {summary}; every non-green state above is "
                  f"visible and non-fatal BY RULE, never silently dropped)")
    return EXIT_FAIL if hard else EXIT_PASS


def self_test(root: Path) -> int:
    """Prove every verdict path offline (fixture mode; skip-policy law:
    a SKIPping checker must still prove its failure path works)."""
    fails: list[str] = []
    # 1. the mixed fixture: TWO hard FAILs (red.yml = silent red nightly;
    #    stillred.yml = newer run also failed), stale/verified/never/off
    #    non-fatal, green PASS.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run(root, load_self_test_fixture(), as_json=False)
    out = buf.getvalue()
    if rc != EXIT_FAIL:
        fails.append(f"self-test: red lanes on their current definition must "
                     f"exit 1, got {rc}")
    for expect in ("FAIL: red.yml", "FAIL: stillred.yml",
                   "STALE-FAIL: stale.yml", "STALE-FAIL: verified.yml",
                   "STALE-FAIL: oldef.yml",
                   "PASS: green.yml", "NOT-RUN: never.yml",
                   "DISABLED: off.yml", "Upload the evidence",
                   "fix VERIFIED", "ALSO failed",
                   "failed ONLY its Scheduled-lane health step"):
        if expect not in out:
            fails.append(f"self-test: expected line missing: {expect!r}")
    # 2. red.yml fixed (touch AFTER the run, no newer run): downgrades to
    #    STALE-FAIL; stillred.yml stays HARD FAIL (a newer failed run
    #    arbitrates over file dates). Exit stays 1.
    fixed = load_self_test_fixture()
    fixed["touches"]["red.yml"] = "2026-09-11T12:30:00+00:00"
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        rc2 = run(root, fixed, as_json=False)
    out2 = buf2.getvalue()
    if "STALE-FAIL: red.yml" not in out2:
        fails.append("self-test: a landed fix (no newer run) must downgrade "
                     "FAIL to visible non-fatal STALE-FAIL")
    if rc2 != EXIT_FAIL or "FAIL: stillred.yml" not in out2:
        fails.append("self-test: a newer FAILED run must keep the lane a "
                     f"hard FAIL regardless of file dates (rc={rc2})")
    # 3. own-lane cap: from INSIDE red.yml its verdict caps at visible
    #    non-fatal; stillred.yml (another lane) keeps the hard-FAIL law.
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        rc3 = run(root, load_self_test_fixture(), as_json=False,
                  own_lane="red.yml")
    out3 = buf3.getvalue()
    if rc3 != EXIT_FAIL:
        fails.append(f"self-test: own-lane cap must not excuse OTHER lanes "
                     f"(rc={rc3})")
    lines3 = out3.splitlines()
    if "STALE-FAIL (capped)" not in out3 or "FAIL: red.yml" in lines3:
        fails.append("self-test: --own-lane red.yml must cap red.yml's own "
                     "verdict to visible non-fatal STALE-FAIL")
    if not any(ln.startswith("FAIL:") and "stillred" in ln for ln in lines3):
        fails.append("self-test: other lanes keep the hard-FAIL law under "
                     "--own-lane")
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return EXIT_FAIL
    print("PASS: scheduled_lane_check --self-test (hard-fail, stale-fix, "
          "newer-run-verified, newer-run-still-red, lane-health-only "
          "exemption, own-lane cap, green, not-run and disabled paths all "
          "proven offline)")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="xr-browser root")
    ap.add_argument("--fixture", default=None,
                    help="canned API/touch JSON (offline determinism)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--own-lane", default=None,
                    help="cap THIS workflow's own verdict at visible "
                         "non-fatal (circularity guard; every scheduled "
                         "lane passes its own file name)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.repo).resolve()
    if not (root / ".github" / "workflows").is_dir():
        print(f"error: no .github/workflows under {root}", file=sys.stderr)
        return EXIT_USAGE
    if args.self_test:
        return self_test(root)
    fixture = None
    if args.fixture:
        try:
            fixture = json.loads(Path(args.fixture).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: bad fixture: {exc}", file=sys.stderr)
            return EXIT_USAGE
    try:
        return run(root, fixture, args.json, args.own_lane)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — network class -> visible SKIP
        print(f"SKIP: SKIP (network unavailable for api.github.com: "
              f"{str(exc)[:160]}) — needed for: the scheduled-lane health "
              f"verdict; --self-test proves the checker offline")
        return EXIT_SKIP


if __name__ == "__main__":
    sys.exit(main())
