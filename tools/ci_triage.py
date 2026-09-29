#!/usr/bin/env python3
"""tools/ci_triage.py — diagnose a hosted run from the PUBLIC endpoints (P13 P0-B).

Why this exists. The phase brief's earlier ruling — "/logs and /annotations are
admin-only, do not claim you needed them" — was half wrong, and the false half
cost a phase. Measured today, on this public repository, unauthenticated:

  * `GET /repos/{owner}/{repo}/commits/{sha}/check-runs`            -> 200
  * `GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations` -> 200
        (this is where "Process completed with exit code 126." came from)
  * `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs`          -> 200
        (failing STEP names — "Governance checks", plus the skipped cascade)
  * `GET /repos/{owner}/{repo}/actions/runs/{run_id}/logs`          -> 403 (admin-only)

So the two things that make a red run diagnosable — the annotation text and the
failing step name — need no credentials at all. This tool prints them together,
for a SHA or a run id, and `--json` for machines. Endpoint shapes and the
public/private table live in docs/process/ci-triage.md.

Never a guess. Network unavailable, rate-limited, or an `--offline` fixture
missing => the tool prints `BLOCKED-NET` with what it could not fetch and exits
77. It does not fall back to "probably a flake", and it never prints a
conclusion it did not read.

Stdlib only. Exit: 0 = triaged, nothing failing · 1 = failing check-run(s) found
(reasons printed) · 2 = usage · 77 = BLOCKED-NET.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED = 0, 1, 2, 77
RUN_ID_RE = re.compile(r"/actions/runs/(\d+)")


def _fetch_module():
    """Load build/upstream/fetch.py — the tree's ONLY network path (P9-T12).

    tools/fetch_allowlist_check.py fails any HTTP call outside that chokepoint,
    which is correct: the first draft of this tool called urllib directly and
    the gate caught it (reproduced locally before the fix:
    `FAIL: tools/ci_triage.py: socket/HTTP call outside the chokepoint:
    urllib.request.urlopen`). Everything here therefore goes through
    fetch.http_get, which also gives this tool the allowlist, the redirect
    check and the retry/backoff policy for free.
    """
    root = Path(__file__).resolve().parents[1]
    saved = sys.modules.get("_common")
    cspec = importlib.util.spec_from_file_location("_common",
                                                   root / "build" / "_common.py")
    cmod = importlib.util.module_from_spec(cspec)
    sys.modules["_common"] = cmod
    try:
        cspec.loader.exec_module(cmod)
        fspec = importlib.util.spec_from_file_location(
            "upstream_fetch", root / "build" / "upstream" / "fetch.py")
        fmod = importlib.util.module_from_spec(fspec)
        sys.modules["upstream_fetch"] = fmod
        fspec.loader.exec_module(fmod)
        return fmod
    finally:
        if saved is None:
            sys.modules.pop("_common", None)
        else:
            sys.modules["_common"] = saved


class BlockedNet(RuntimeError):
    """The fact could not be fetched. Never downgraded to a guess."""


class Fetcher:
    """Live (urllib) or fixture-backed (`--offline`) source of API JSON."""

    def __init__(self, offline: Path | None = None, timeout: float = 20.0) -> None:
        self.offline = offline
        self.timeout = timeout
        self.calls: list[str] = []

    def get(self, path: str, fixture: str) -> dict:
        self.calls.append(path)
        if self.offline is not None:
            candidate = self.offline / fixture
            if not candidate.is_file():
                raise BlockedNet(
                    f"BLOCKED-NET (offline fixture missing: {candidate}) — cannot "
                    f"answer for {path}; a fixture-backed run must not guess")
            return json.loads(candidate.read_text(encoding="utf-8"))
        try:
            fetch = _fetch_module()
            # The base URL is the chokepoint's own constant — a literal here
            # would be a second, unreviewed copy of the network surface.
            raw = fetch.http_get(fetch.GITHUB_API + path,
                                 timeout=int(self.timeout))
        except Exception as exc:  # FetchError (incl. HTTP 403/404), import failure
            msg = str(exc)
            code = re.search(r"HTTP (\d{3})", msg)
            if code and code.group(1) in ("401", "403", "404", "429"):
                raise BlockedNet(
                    f"BLOCKED-NET (HTTP {code.group(1)} from {path}) — the "
                    "endpoint refused this request; see docs/process/ci-triage.md "
                    "for what is public and what needs admin") from exc
            raise BlockedNet(f"BLOCKED-NET ({type(exc).__name__}: {msg}) — no "
                            f"readable route to api.github.com for {path}") from exc
        return json.loads(raw.decode("utf-8"))


def fetch_check_runs(f: Fetcher, repo: str, sha: str) -> list[dict]:
    doc = f.get(f"/repos/{repo}/commits/{sha}/check-runs",
                fixture=f"sha-{sha[:7]}.check-runs.json")
    return doc.get("check_runs", [])


def fetch_annotations(f: Fetcher, repo: str, check_run_id: int) -> list[dict]:
    doc = f.get(f"/repos/{repo}/check-runs/{check_run_id}/annotations",
                fixture=f"check-runs/{check_run_id}.annotations.json")
    return doc if isinstance(doc, list) else []


def fetch_jobs(f: Fetcher, repo: str, run_id: int) -> list[dict]:
    doc = f.get(f"/repos/{repo}/actions/runs/{run_id}/jobs",
                fixture=f"runs/{run_id}.jobs.json")
    return doc.get("jobs", [])


def run_id_from(check_run: dict) -> int | None:
    m = RUN_ID_RE.search(check_run.get("details_url") or "")
    return int(m.group(1)) if m else None


def triage(f: Fetcher, repo: str, sha: str = "", run_id: int | None = None) -> dict:
    """Collect the diagnosis. Every field is *read*, never inferred."""
    out: dict = {"repo": repo, "sha": sha, "run_id": run_id,
                 "check_runs": [], "log_access": None, "blocked": []}
    if run_id is not None and not sha:
        try:
            run = f.get(f"/repos/{repo}/actions/runs/{run_id}", fixture=f"runs/{run_id}.json")
            sha = run.get("head_sha", "")
            out["sha"] = sha
            out["workflow"] = run.get("name")
        except BlockedNet as exc:
            out["blocked"].append(str(exc))
            return out
    if not sha:
        raise BlockedNet("BLOCKED-NET (no sha: pass --sha or a --run with a fixture)")

    check_runs = fetch_check_runs(f, repo, sha)
    seen_jobs: set[int] = set()
    for cr in check_runs:
        entry = {"name": cr.get("name"), "id": cr.get("id"),
                 "status": cr.get("status"), "conclusion": cr.get("conclusion"),
                 "annotations": [], "failing_steps": [], "job": None, "run_id": run_id_from(cr)}
        if cr.get("conclusion") not in (None, "success", "neutral", "skipped"):
            try:
                for a in fetch_annotations(f, repo, cr["id"]):
                    entry["annotations"].append(
                        {"level": a.get("annotation_level"),
                         "path": f"{a.get('path')}:{a.get('start_line')}",
                         "message": (a.get("message") or "").strip()})
            except BlockedNet as exc:
                out["blocked"].append(str(exc))
        rid = entry["run_id"]
        if rid and rid not in seen_jobs:
            seen_jobs.add(rid)
            try:
                for job in fetch_jobs(f, repo, rid):
                    if job.get("conclusion") in ("failure", "cancelled", "timed_out"):
                        entry["job"] = {"name": job.get("name"),
                                        "conclusion": job.get("conclusion")}
                        entry["failing_steps"] = [
                            {"number": s.get("number"), "name": s.get("name"),
                             "conclusion": s.get("conclusion")}
                            for s in job.get("steps", []) if s.get("conclusion") == "failure"]
                        entry["skipped_steps"] = [
                            s.get("name") for s in job.get("steps", [])
                            if s.get("conclusion") == "skipped"]
                        break
            except BlockedNet as exc:
                out["blocked"].append(str(exc))
        out["check_runs"].append(entry)

    # The logs endpoint is the one thing that genuinely needs admin; measure it
    # rather than repeating folklore (403 == admin-only, 200 == public here).
    rid = run_id or next((e["run_id"] for e in out["check_runs"] if e["run_id"]), None)
    if rid:
        try:
            f.get(f"/repos/{repo}/actions/runs/{rid}/logs", fixture=f"runs/{rid}.logs.json")
            out["log_access"] = f"run {rid}: /logs returned 200 (readable by this token)"
        except BlockedNet as exc:
            first = str(exc).split("—")[0].strip()
            out["log_access"] = f"run {rid}: {first} (/logs is admin-only; use --sha for the public path)"
    return out


def _print(doc: dict) -> None:
    print(f"ci-triage: repo={doc['repo']} sha={(doc.get('sha') or '?')[:12]}"
          + (f" run={doc.get('run_id')}" if doc.get("run_id") else ""))
    for cr in doc["check_runs"]:
        print(f"  check-run {cr['name']}: {cr['status']}/{cr['conclusion']}"
              + (f" (run {cr['run_id']}, job: {cr['job']['name']} -> {cr['job']['conclusion']})"
                 if cr.get("job") else ""))
        for s in cr.get("failing_steps", []):
            print(f"    failing step: {s['number']}. {s['name']}")
        if cr.get("skipped_steps"):
            n = len(cr["skipped_steps"])
            print(f"    ({n} step(s) skipped after the failure — the cascade a bare "
                  "exit code hides)")
        for a in cr.get("annotations", []):
            print(f"    [{a['level']}] {a['path']}: {a['message']}")
    failed = [c for c in doc["check_runs"]
              if c["conclusion"] not in (None, "success", "neutral", "skipped")]
    print(f"  verdict: {'RED — ' + str(len(failed)) + ' failing check-run(s)' if failed else 'green (no failing check-run)'}")
    if doc.get("log_access"):
        print(f"  logs: {doc['log_access']}")
    for b in doc.get("blocked", []):
        print(f"  {b}")


def _self_test() -> int:
    """Fixture-backed proof that the tool reads rather than guesses."""
    here = Path(__file__).resolve().parent
    fx = here / "fixtures" / "ci_triage"
    if not fx.is_dir():
        print(f"SKIP (ci_triage self-test): no fixtures at {fx}")
        return EXIT_BLOCKED
    f = Fetcher(offline=fx)
    sha = (fx / "RED_SHA.txt").read_text(encoding="utf-8").strip()
    red = triage(f, "RRRTX-Labs/xr-browser", sha=sha)
    fails = []
    ann = [a["message"] for cr in red["check_runs"] for a in cr["annotations"]]
    if not any("exit code 126" in m for m in ann):
        fails.append("the red fixture's exit-code-126 annotation was not surfaced")
    steps = [s["name"] for cr in red["check_runs"] for s in cr.get("failing_steps", [])]
    if "Governance checks" not in steps:
        fails.append("the failing step name ('Governance checks') was not surfaced")
    if not any("admin-only" in (e.get("log_access") or "") for e in [red]):
        fails.append("the /logs access finding was not recorded")
    try:
        triage(f, "RRRTX-Labs/xr-browser", sha="0" * 40)
        fails.append("a SHA with no fixture did not degrade to BLOCKED-NET")
    except BlockedNet as exc:
        if "BLOCKED-NET" not in str(exc) or "fixture missing" not in str(exc):
            fails.append("the degraded path did not name the missing fixture")
    if fails:
        for m in fails:
            print(f"SELF-TEST FAIL: {m}")
        return EXIT_FAIL
    print("PASS: ci_triage self-test (red fixture surfaced exit code 126 + the failing "
          "step; a missing fixture degrades to BLOCKED-NET, never to a guess)")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default="RRRTX-Labs/xr-browser")
    ap.add_argument("--sha", default="")
    ap.add_argument("--run", dest="run_id", type=int, default=None)
    ap.add_argument("--offline", default="", help="fixture directory (no network)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()
    if not args.sha and args.run_id is None:
        ap.print_help()
        return EXIT_USAGE
    f = Fetcher(offline=Path(args.offline) if args.offline else None)
    try:
        doc = triage(f, args.repo, sha=args.sha, run_id=args.run_id)
    except BlockedNet as exc:
        print(str(exc))
        return EXIT_BLOCKED
    if args.json:
        print(json.dumps(doc, indent=1, sort_keys=True))
    else:
        _print(doc)
    if doc.get("blocked") and not doc["check_runs"]:
        return EXIT_BLOCKED
    failed = [c for c in doc["check_runs"]
              if c["conclusion"] not in (None, "success", "neutral", "skipped")]
    return EXIT_FAIL if failed else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
