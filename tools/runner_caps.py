#!/usr/bin/env python3
"""tools/runner_caps.py — the runner-capabilities ledger (P11-T0-d).

`docs/state/runner-capabilities.json` records what the HOSTED runner
(ubuntu-latest) actually carries — and what it does NOT — with every entry
proven by a real run. The law this file enforces:

  * `present: true/false` REQUIRES a non-empty `proven_by` list, and each
    proof cites a real hosted observation: `ci_run` + `ci_job` ids, or a
    `log` path (for negative observations recorded from run transcripts),
    plus `date`. A capability asserted from a workflow COMMENT, a docs
    claim or belief is refused — P10's research item 8 exists because
    "ubuntu-latest ships Rust and Go" was a comment, and the Go half was
    never observed by any lane (it stays UNOBSERVED here);
  * `present: "UNOBSERVED"` requires a `note` saying why, and must not
    carry a `version`;
  * a `version` string requires `present: true`.

The ledger has one consumer with teeth: evidence_check --strict rule (e)
— a BLOCKED-* row whose blocker is "no <tool>" while the ledger (or this
sandbox) proves the tool PRESENT is STALE and FAILs: re-run and record, or
record why presence still blocks. `stale_blocked_findings()` implements it;
evidence_check.py calls it for P9+ bundles under --strict.

CLI: --check validates the ledger (exit 0/1); --json machine output;
--self-test proves both refusal laws and the stale-BLOCKED rule offline.
Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

CAPS_RELPATH = "docs/state/runner-capabilities.json"
EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def load_caps(repo: Path) -> dict[str, Any] | None:
    """The ledger, or None when absent (callers must SKIP visibly)."""
    p = repo / CAPS_RELPATH
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_invalid": str(p)}
    return doc if isinstance(doc, dict) else {"_invalid": str(p)}


def check_caps(doc: dict[str, Any], where: str) -> list[str]:
    """Citation-law findings for a ledger document."""
    fails: list[str] = []
    if "_invalid" in doc:
        return [f"{where}: not a valid JSON object"]
    caps = doc.get("capabilities")
    if not isinstance(caps, dict) or not caps:
        return [f"{where}: 'capabilities' must be a non-empty object "
                "(zero-case law: an empty ledger certifies nothing)"]
    for tool, ent in caps.items():
        if not isinstance(ent, dict):
            fails.append(f"{where}: capability {tool!r} must be an object")
            continue
        present = ent.get("present")
        proofs = ent.get("proven_by") or []
        if present is True or present is False:
            if not isinstance(proofs, list) or not proofs:
                fails.append(
                    f"{where}: capability {tool!r} present={present} with no "
                    "proven_by — a capability asserted from a comment or "
                    "belief is refused; cite the real run(s) (ci_run+ci_job) "
                    "or the transcript log that observed it")
            for i, pr in enumerate(proofs):
                if not isinstance(pr, dict):
                    fails.append(f"{where}: {tool!r} proven_by[{i}] not an object")
                    continue
                if not pr.get("date"):
                    fails.append(f"{where}: {tool!r} proven_by[{i}] has no date")
                if not ((pr.get("ci_run") and pr.get("ci_job")) or pr.get("log")):
                    fails.append(
                        f"{where}: {tool!r} proven_by[{i}] cites neither "
                        "ci_run+ci_job nor a log path — nothing to resolve")
        elif present == "UNOBSERVED":
            if not ent.get("note"):
                fails.append(f"{where}: capability {tool!r} UNOBSERVED needs "
                             "a note saying why (and it must never grow a "
                             "version without a run that printed one)")
            if ent.get("version"):
                fails.append(f"{where}: capability {tool!r} UNOBSERVED must "
                             "not carry a version")
        else:
            fails.append(f"{where}: capability {tool!r} present must be "
                         "true/false/\"UNOBSERVED\"")
        if ent.get("version") and present is not True:
            fails.append(f"{where}: capability {tool!r} carries a version "
                         "but present is not true")
    return fails


def _absent_claim_re(tool: str) -> re.Pattern[str]:
    t = re.escape(tool)
    return re.compile(
        rf"\bno\s+{t}\b|\bwithout\s+{t}\b|\b{t}\b[^.{{}}]{{0,40}}?"
        rf"\b(?:absent|missing|unavailable|not\s+(?:available|installed|"
        rf"present|in))\b", re.I)


def stale_blocked_findings(rows: list[dict], caps: dict[str, Any],
                           where: str) -> list[str]:
    """Rule (e): a BLOCKED-* row whose blocker tool is PROVEN PRESENT
    (hosted ledger or this sandbox) is stale — the block reason no longer
    holds and the row must be re-run and re-recorded (or re-argued)."""
    fails: list[str] = []
    capabilities = caps.get("capabilities") or {}
    for row in rows:
        status = str(row.get("status", ""))
        if not status.upper().startswith("BLOCKED"):
            continue
        rid = row.get("id", "<no id>")
        text = " ".join(
            str(x) for x in [row.get("dod", ""), row.get("notes", "")]
            + [str(e) for e in (row.get("evidence") or [])])
        for tool, ent in capabilities.items():
            if not isinstance(ent, dict) or ent.get("present") is not True:
                continue
            if _absent_claim_re(tool).search(text):
                runs = ", ".join(
                    str(p.get("ci_run")) for p in (ent.get("proven_by") or [])
                    if isinstance(p, dict) and p.get("ci_run"))
                fails.append(
                    f"{where}: row {rid} is BLOCKED on absent {tool!r}, but "
                    f"the runner-capabilities ledger proves it PRESENT "
                    f"(hosted run(s) {runs or '?'}) — STALE BLOCKED: re-run "
                    "and record, or record why presence still blocks "
                    "(P11-T0-d rule e)")
        # the same law against THIS sandbox (a local-run blocker that the
        # local toolchain disproves today)
        for tool in ("cargo", "rustc", "go", "g++", "clang", "make",
                     "semgrep"):
            if shutil.which(tool) and _absent_claim_re(tool).search(text):
                fails.append(
                    f"{where}: row {rid} is BLOCKED on absent {tool!r}, but "
                    f"`which {tool}` resolves HERE — STALE BLOCKED (P11-T0-d "
                    "rule e, local arm)")
    return fails


SELF_TEST_LEDGER = {
    "capabilities": {
        "cargo": {"present": True, "version": "1.98.1",
                  "proven_by": [{"ci_run": 1, "ci_job": 2,
                                 "date": "2026-09-11"}]},
        "go": {"present": "UNOBSERVED", "note": "no lane ever printed it"},
    },
}


def self_test() -> int:
    fails: list[str] = []
    # ledger citation law
    if check_caps(SELF_TEST_LEDGER, "selftest") != []:
        fails.append("self-test: a fully cited ledger must pass")
    bad = json.loads(json.dumps(SELF_TEST_LEDGER))
    bad["capabilities"]["rustc"] = {"present": True, "version": "1.98.1"}
    if not any("no\n" not in f and "proven_by" in f
               for f in check_caps(bad, "selftest")):
        fails.append("self-test: present:true without proven_by must be "
                     "refused")
    bad2 = json.loads(json.dumps(SELF_TEST_LEDGER))
    bad2["capabilities"]["go"] = {"present": "UNOBSERVED"}
    if not check_caps(bad2, "selftest"):
        fails.append("self-test: UNOBSERVED without a note must be refused")
    if not check_caps({"capabilities": {}}, "selftest"):
        fails.append("self-test: an empty ledger must be refused")
    # rule (e): stale BLOCKED
    rows = [{"id": "X-1", "status": "BLOCKED-NET",
             "dod": "deployable check — no cargo in the sandbox",
             "evidence": ["logs/x.txt"]}]
    hits = stale_blocked_findings(rows, SELF_TEST_LEDGER, "selftest")
    if not any("STALE BLOCKED" in h and "cargo" in h for h in hits):
        fails.append("self-test: BLOCKED-on-cargo with cargo proven present "
                     "must be flagged stale")
    rows_ok = [{"id": "X-2", "status": "BLOCKED-NET",
                "dod": "needs the farm VM (browser+display)",
                "evidence": ["logs/y.txt"]}]
    local_hits = [h for h in stale_blocked_findings(rows_ok, SELF_TEST_LEDGER,
                                                    "selftest")
                  if "local arm" in h]
    if local_hits:
        fails.append(f"self-test: a non-tool block reason must not fire: "
                     f"{local_hits}")
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return EXIT_FAIL
    print("PASS: runner_caps --self-test (citation law + UNOBSERVED law + "
          "empty-ledger law + stale-BLOCKED rule, all proven offline)")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="repository root")
    ap.add_argument("--check", action="store_true",
                    help="validate the ledger's citation law")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    repo = Path(args.repo).resolve()
    doc = load_caps(repo)
    if doc is None:
        print(f"FAIL: no ledger at {repo / CAPS_RELPATH} — the T0-d law "
              "says the ledger EXISTS and is cited; an absent ledger fails "
              "--check (evidence_check SKIPs rule (e) visibly instead)")
        return EXIT_FAIL
    findings = check_caps(doc, CAPS_RELPATH)
    if args.json:
        print(json.dumps({"status": "fail" if findings else "pass",
                          "findings": findings,
                          "capabilities": sorted(
                              (doc.get("capabilities") or {}).keys())},
                         indent=2))
    else:
        for f in findings:
            print(f"FAIL: {f}")
        if not findings:
            caps = doc.get("capabilities") or {}
            print(f"PASS: runner-capabilities ledger ({len(caps)} entries, "
                  "every present/absent claim cited by a real run or "
                  "transcript; UNOBSERVED entries say why)")
    return EXIT_FAIL if findings else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
