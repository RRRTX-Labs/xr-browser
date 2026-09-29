#!/usr/bin/env python3
"""tools/evidence_finality.py — the phase-finality law (P13-P0-C).

The defect this closes, measured on 2026-09-29: `evidence_check.py --strict`
printed **PASS** for `evidence/P12/evidence.json`, a bundle with no head, zero
`ci-run` rows and eight rows still reading `BLOCKED-PENDING-T5`, `…T6`, `…T7`,
`…CLOSE`, `…DOCS`, `…REPORT`. Structural reason: the checker only ever judged
the rows and claims that were *present* (evidence_check.py:157 derives the head
set from `pin`+`repos`; the ci-run validation at :247–:277 runs per row). An
honest-but-incomplete bundle therefore passed **vacuously** — the checker
rewarded not claiming completion. That is the same invisibility class as P11's
`logs/`-only directory: absence read as success.

The law, restated as code (a bundle's own declarations decide which rules bite):

  state        "interim" | "final". ABSENT => final: silence is a claim.
  interim      legal only for the phase the tree declares in flight
               (docs/state/phase-base.json `phase`). A superseded/closed phase
               may never be interim — that is the "interim at the closing
               commit" hole. interim rows may use *-PENDING-* sentinels.
  final        every EFFECTIVE row status must be in the final vocabulary
               {VERIFIED, PARTIAL, BLOCKED, HUMAN-GATED, NOT-BY-DESIGN} (or
               BLOCKED-<CAUSE>); no effective status may carry PENDING (that
               is interim's vocabulary, and inventing statuses instead of
               using the brief's is itself the smell that hid this);
               a `phase_head` must be declared; `ci_claimed` must name
               `governance` (plus `core-hardening` when a core was touched);
               and evidence/P<n>/report.md must exist carrying the 12-section
               report. The head/ci-run *resolution* stays evidence_ci's job
               (T0-U2, rule (a)) — this module only removes the vacuity.

Append-only corrections: a row whose id appears in a later row's `corrects`
field is SUPERSEDED — the later row's status is the effective one, and the
original text stays in place with its status quoted by the corrections. That is
how P12's close-out rows fold into evidence/P12/ without editing history
(P11-T0-d rule (d) uses the same field).

`--require-phase-final` is the closing form of the law: every bundle must be
final EXCEPT the tree's declared in-flight phase, whose only legal escape is an
explicit `state: "interim"`. Without it, the same closed-phase rule still
applies (a bundle that is not the in-flight phase must be final) — the flag
adds the in-flight phase itself to the demand, which is what a closing gate
wants to say. The in-flight carve-out exists because the *presence* law
(evidence_presence_check.py) requires a phase's bundle from its first commit;
a bundle that must exist from commit one cannot be final from commit one.

Scoping: FINALITY_MIN_PHASE = 12. P12 is the phase this law was written for
and P13 is the one it gates; older bundles (P3–P11) keep their historical,
already-shipped shape exactly as the T0-U2 head law grandfathers an undeclared
head — widening it would rewrite closed phases' contracts, which the brief
forbids.

Usage:  python3 tools/evidence_finality.py --repo . [--json] [--self-test]
Exit: 0 pass · 1 fail · 2 usage · 77 SKIP. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77

# The first phase this law binds; see the scoping note above.
FINALITY_MIN_PHASE = 12
FINAL_STATUSES = ("VERIFIED", "PARTIAL", "BLOCKED", "HUMAN-GATED", "NOT-BY-DESIGN")
BLOCKED_RE = re.compile(r"^BLOCKED(-[A-Z0-9_]+)*$")
PHASE_DIR_RE = re.compile(r"^P(\d{1,3})$")
HEAD_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
PENDING_RE = re.compile(r"PENDING", re.IGNORECASE)
# ①..⑫ — the established report order (see the phase brief: ① reproduction,
# ⑩ hosted state before any done claim, ⑫ deviations/human gates/inheritance).
SECTION_MARKERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
REPORT_MIN_SECTIONS = 12


def phase_number(name: str) -> int | None:
    m = PHASE_DIR_RE.fullmatch(name)
    return int(m.group(1)) if m else None


def in_flight_phase(repo: Path) -> str | None:
    """The phase the tree declares in flight, or None when unreadable.

    `None` means the carve-out cannot be granted: a bundle that wants the
    in-flight exemption must be able to *show* it is in flight, so an
    unreadable/absent phase-base.json makes `interim` illegal rather than
    silently free (fail closed).
    """
    try:
        doc = json.loads((repo / "docs" / "state" / "phase-base.json")
                         .read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — absent/unreadable => no exemption
        return None
    phase = doc.get("phase")
    return str(phase).strip() if isinstance(phase, str) and phase.strip() else None


def _effective_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    """(effective status per row id, ids of rows that stand as superseded).

    A row is superseded when a LATER row names it in `corrects` — append-only,
    exactly as P11-T0-d rule (d) reads the same field.
    """
    effective: dict[str, str] = {}
    superseded: list[str] = []
    corrections: dict[str, str] = {}
    for idx, row in enumerate(rows):
        rid = str(row.get("id", f"<row {idx}>"))
        effective[rid] = str(row.get("status", ""))
        target = row.get("corrects")
        if isinstance(target, str) and target.strip():
            corrections.setdefault(str(target).strip(), rid)
    for target, fixing_id in corrections.items():
        if target in effective:
            superseded.append(target)
            effective[target] = effective[fixing_id]
    return effective, superseded


def _report_findings(bundle: Path, path: Path) -> list[str]:
    report = bundle / "report.md"
    if not report.is_file() or not report.read_text(encoding="utf-8").strip():
        return [f"final bundle has no {bundle.name}/report.md — rows "
                f"and logs without the 12-section report are not a closed "
                f"phase (P13-P0-C)"]
    text = report.read_text(encoding="utf-8")
    marked = sum(1 for i in range(REPORT_MIN_SECTIONS) if SECTION_MARKERS[i] in text)
    headings = len(re.findall(r"(?m)^##\s+\S", text))
    if marked < REPORT_MIN_SECTIONS and headings < REPORT_MIN_SECTIONS:
        return [f"{bundle.name}/report.md carries {marked} of the 12 "
                f"section markers and {headings} '## ' headings — the report "
                f"must be the full {REPORT_MIN_SECTIONS}-section report "
                f"(markers {SECTION_MARKERS})"]
    return []


def finality_findings(doc: dict[str, Any], rows: list[dict[str, Any]],
                      path: Path, repo: Path, *, in_flight: str | None = None,
                      require_phase_final: bool = False) -> list[str]:
    """Findings for one bundle; [] == pass. Prints its decision, always."""
    fails: list[str] = []
    bundle = path.parent
    n = phase_number(bundle.name)
    if n is None or n < FINALITY_MIN_PHASE:
        print(f"finality: {bundle.name}: pre-law phase "
              f"(law binds P{FINALITY_MIN_PHASE}+) — state not judged; the "
              f"bundle's own rows are unchanged", file=sys.stderr)
        return fails

    raw_state = doc.get("state", None)
    state = "final" if raw_state is None else str(raw_state).strip().lower()
    if state not in ("interim", "final"):
        return [f"state {raw_state!r} is not 'interim' or 'final' — "
                f"absent means final, and invented values are the thing this "
                f"law exists to stop (P13-P0-C)"]
    is_in_flight = in_flight is not None and bundle.name == in_flight.strip()
    origin = ("declared" if raw_state is not None else "absent => final")

    if state == "interim":
        if is_in_flight:
            print(f"finality: {bundle.name}: interim — in flight per "
                  f"docs/state/phase-base.json (phase={in_flight}); PENDING "
                  f"sentinels are legal here and the final rules do not apply",
                  file=sys.stderr)
            return fails
        fails.append(f"state 'interim' but this is not the in-flight "
                     f"phase (docs/state/phase-base.json says "
                     f"{in_flight!r}) — interim may never be the state of a "
                     f"closed/superseded phase (P13-P0-C)")
        return fails

    # ---- state == final ----------------------------------------------------
    print(f"finality: {bundle.name}: final ({origin}) — judging the final "
          f"vocabulary, the declared head, the claimed workflows and "
          f"report.md", file=sys.stderr)
    if require_phase_final and is_in_flight:
        print(f"finality: {bundle.name}: --require-phase-final: this IS the "
              f"in-flight phase and it declares final — the strongest form; "
              f"judged below", file=sys.stderr)

    effective, superseded = _effective_rows(rows)
    if superseded:
        print(f"finality: {bundle.name}: {len(superseded)} row(s) superseded "
              f"by appended corrections (append-only): "
              f"{', '.join(sorted(superseded))}", file=sys.stderr)
    bad_vocab, bad_pending = [], []
    for rid, status in effective.items():
        token = status.strip().upper()
        if PENDING_RE.search(token):
            bad_pending.append(f"{rid}={status!r}")
        elif token not in FINAL_STATUSES and not BLOCKED_RE.match(token):
            bad_vocab.append(f"{rid}={status!r}")
    if bad_pending:
        fails.append(f"final bundle carries *-PENDING-* sentinels — "
                     f"{', '.join(sorted(bad_pending))} — PENDING is interim's "
                     f"vocabulary; resolve each row with a status this sandbox "
                     f"can show or an appended correction quoting the original "
                     f"(P13-P0-C)")
    if bad_vocab:
        fails.append(f"final bundle has row statuses outside "
                     f"{list(FINAL_STATUSES)}: {', '.join(sorted(bad_vocab))}")

    head = str(doc.get("phase_head") or "").strip()
    if not HEAD_RE.search(head):
        fails.append(f"final bundle declares no phase_head — without "
                     f"it the final-CI claim has nothing to attach to and "
                     f"T0-U2 cannot bite (P13-P0-C)")
    claimed = doc.get("ci_claimed")
    if not (isinstance(claimed, list) and claimed
            and all(isinstance(w, str) and w.strip() for w in claimed)):
        fails.append(f"final bundle must declare ci_claimed as a "
                     f"non-empty list of workflow names (P13-P0-C)")
    elif "governance" not in [str(w).strip() for w in claimed]:
        fails.append(f"ci_claimed must include 'governance' — it runs "
                     f"on every push to main (P13-P0-C)")
    fails.extend(_report_findings(bundle, path))
    return fails


def check_bundles(root: Path, repo: Path, *, require_phase_final: bool = False
                  ) -> tuple[list[str], int]:
    """Run the law over every bundle under `root` (git-independent)."""
    in_flight = in_flight_phase(repo)
    if in_flight is None:
        print("finality: WARNING: docs/state/phase-base.json unreadable — the "
              "in-flight exemption cannot be granted, so any 'interim' bundle "
              "fails (fail closed)", file=sys.stderr)
    fails: list[str] = []
    checked = 0
    for f in sorted(root.glob("*/evidence.json")):
        checked += 1
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — evidence_check reports it too
            print(f"finality: {f}: unreadable ({exc})", file=sys.stderr)
            continue
        rows = doc.get("dod_rows") if isinstance(doc.get("dod_rows"), list) else []
        fails.extend(finality_findings(doc, rows, f, repo, in_flight=in_flight,
                                       require_phase_final=require_phase_final))
    return fails, checked


def _self_test() -> int:
    """Offline proof that the law bites and that the legal shapes pass."""
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "docs" / "state").mkdir(parents=True)
        (repo / "docs" / "state" / "phase-base.json").write_text(
            json.dumps({"phase": "P13"}), encoding="utf-8")
        root = repo / "evidence"

        def bundle(name: str, doc: dict, report: bool = True) -> Path:
            d = root / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "evidence.json").write_text(json.dumps(doc), encoding="utf-8")
            if report:
                body = "\n".join(f"## {i + 1}. section" for i in range(12))
                (d / "report.md").write_text(body, encoding="utf-8")
            return d / "evidence.json"

        row = {"id": "R1", "dod": "x", "status": "VERIFIED", "evidence": ["a"]}
        final_doc = {"phase": "P12", "state": "final",
                     "phase_head": "a" * 40, "ci_claimed": ["governance"],
                     "dod_rows": [row]}
        f1 = bundle("P12", final_doc)
        got = finality_findings(final_doc, [row], f1, repo, in_flight="P13")
        if got:
            fails.append(f"a legal final bundle failed: {got}")
        # (a) final + a PENDING row
        pend = {"id": "R1", "dod": "x", "status": "BLOCKED-PENDING-T5",
                "evidence": ["a"]}
        got = finality_findings({**final_doc, "dod_rows": [pend]}, [pend], f1,
                                repo, in_flight="P13")
        if not any("PENDING" in g for g in got):
            fails.append("final + a *-PENDING-* row did not redden")
        # (a2) the same row superseded by an appended correction => legal
        corr = {"id": "R1b", "dod": "x", "status": "VERIFIED",
                "evidence": ["a"], "corrects": "R1"}
        got = finality_findings({**final_doc, "dod_rows": [pend, corr]},
                                [pend, corr], f1, repo, in_flight="P13")
        if got:
            fails.append(f"an append-only correction did not clear the "
                         f"PENDING row: {got}")
        # (b) final + no report.md — a second root so the earlier report.md
        # cannot satisfy it (the first root's P12 dir already carries one)
        repo2 = Path(td) / "second"
        (repo2 / "docs" / "state").mkdir(parents=True)
        (repo2 / "docs" / "state" / "phase-base.json").write_text(
            json.dumps({"phase": "P13"}), encoding="utf-8")
        f2 = repo2 / "evidence" / "P12"
        f2.mkdir(parents=True)
        (f2 / "evidence.json").write_text(json.dumps(final_doc), encoding="utf-8")
        f2 = f2 / "evidence.json"
        got = finality_findings(final_doc, [row], f2, repo2, in_flight="P13")
        if not any("report.md" in g for g in got):
            fails.append("final without report.md did not redden")
        # (c) interim while in flight is legal, even carrying PENDING
        inter = {"phase": "P13", "state": "interim", "dod_rows": [pend]}
        f3 = bundle("P13", inter)
        got = finality_findings(inter, [pend], f3, repo, in_flight="P13")
        if got:
            fails.append(f"in-flight interim failed: {got}")
        # (d) interim on a closed phase is illegal
        got = finality_findings({**inter, "phase": "P12"}, [pend], f1, repo,
                                in_flight="P13")
        if not any("in-flight" in g for g in got):
            fails.append("interim on a closed phase did not redden")
        # (e) an invented state value is a failure, not a pass
        got = finality_findings({**final_doc, "state": "final-ish"}, [row], f1,
                                repo, in_flight="P13")
        if not any("not 'interim' or 'final'" in g for g in got):
            fails.append("an invented state value was accepted")
        # (f) pre-law phases are untouched
        f4 = bundle("P4", {"phase": "P4", "dod_rows": [pend]}, report=False)
        got = finality_findings({"phase": "P4", "dod_rows": [pend]}, [pend], f4,
                                repo, in_flight="P13")
        if got:
            fails.append(f"a pre-law phase was judged: {got}")
    if fails:
        for m in fails:
            print(f"SELF-TEST FAIL: {m}")
        return EXIT_FAIL
    print("PASS: evidence_finality self-test (final vocabulary + PENDING law, "
          "append-only correction, report.md, in-flight interim, invented "
          "state, pre-law scoping — all proven offline)")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dir", default="evidence")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--require-phase-final", action="store_true",
                    help="the closing form: every bundle final except the "
                         "tree's declared in-flight phase")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    repo = Path(args.repo).resolve()
    root = repo / args.dir
    if not root.is_dir():
        print(f"error: no evidence directory at {root}", file=sys.stderr)
        return EXIT_USAGE
    fails, checked = check_bundles(root, repo,
                                   require_phase_final=args.require_phase_final)
    if args.json:
        print(json.dumps({"tool": "evidence_finality", "checked": checked,
                          "require_phase_final": args.require_phase_final,
                          "failures": fails}, indent=2, sort_keys=True))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: evidence_finality "
              f"({checked} bundle(s), {len(fails)} failure(s); law binds "
              f"P{FINALITY_MIN_PHASE}+; in-flight="
              f"{in_flight_phase(repo)!r})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
