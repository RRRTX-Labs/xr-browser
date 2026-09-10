#!/usr/bin/env python3
"""tools/sast_check.py — the SAST rule-registry gate (P9-T9).

Plan P9-T9 names clang-tidy custom checks, rust-clippy/cargo-vet/cargo-audit,
and Semgrep banned-API rules. None of those tools can run in the P9 sandbox
(no clang, no rustc, and semgrep is a new host) — so this tool is the
in-sandbox gate over build/sast/rules/sast-rules.yaml, and the tool binaries
run CI-side (HG-30), recorded with their exact commands.

The gate enforces:
  1. EMPTY-RUN — a registry with zero active rules is a failure.
  2. CANARY — every active rule's fixture must exist AND contain one of the
     rule's literal patterns (a rule that can't turn red is theater).
  3. REAL-TREE CLEAN — the literal patterns, scanned over the rule's scope
     (core paths / ui / tools), must have zero hits in the shipped tree.
     build/sast/fixtures/ is never a scope: it exists only to trip the rule.
  4. NO FALSE POSITIVE — every negative fixture must trip no pattern.
  5. OWNED NOT-YET — every not_yet rule names an owner phase and a fixture.
  6. CI READY — every Semgrep file parses as YAML with a rules: list; every
     CI gate records a ci_command.

mode_lint rules delegate enforcement to tools/mode_lint.py (exit 0 required).
Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, \
    RunnerError, require_cases  # noqa: E402

RULES_YAML = "build/sast/rules/sast-rules.yaml"
FIXTURES = "build/sast/fixtures"
SEMGREP_DIR = "build/sast/rules/semgrep"


def load_registry(repo: Path) -> dict:
    import yaml
    p = repo / RULES_YAML
    if not p.exists():
        raise RunnerError(f"missing {RULES_YAML}")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise RunnerError(f"{RULES_YAML}: unsupported schema_version")
    return doc


def scan_scope(repo: Path, rule: dict) -> list[str]:
    hits: list[str] = []
    pats = [p for p in rule.get("patterns") or [] if p]
    if not pats:
        return hits
    exts = set(rule.get("exts") or [".cc", ".h"])
    seen: set[Path] = set()
    for scope in rule.get("scope") or []:
        root = Path(scope)
        if not root.is_absolute():
            root = repo / root
        root = root.resolve()
        if not root.exists():
            continue
        for f in sorted(root.rglob("*")):
            if f.suffix not in exts or f.is_dir():
                continue
            if "node_modules" in f.parts or f.suffix == ".d.ts":
                continue
            if f in seen:
                continue
            seen.add(f)
            if "build/sast/fixtures" in str(f):
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for pat in pats:
                if pat in text:
                    line = text[:text.index(pat)].count("\n") + 1
                    hits.append(f"{f}:{line}: {pat!r} "
                                f"(rule {rule['id']})")
    return hits


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="sast_check", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        doc = load_registry(repo)
    except RunnerError as exc:
        print(f"FAIL: {exc}")
        return EXIT_FAIL
    rules = list(doc.get("rules") or [])
    fails: list[str] = []

    active = [r for r in rules if r.get("status", "active") == "active"]
    if not active:
        fails.append("zero active rules (empty-run law)")

    for rule in rules:
        rid = rule.get("id")
        fixture = repo / rule["fixture"]
        if not fixture.exists():
            fails.append(f"{rid}: fixture missing: {rule['fixture']}")
            continue
        if rule.get("status", "active") == "not_yet":
            if not rule.get("owner_phase"):
                fails.append(f"{rid}: not_yet rule with no owner_phase")
            continue
        pats = [x for x in rule.get("patterns") or [] if x]
        text = fixture.read_text(encoding="utf-8", errors="replace")
        if pats and not any(pat in text for pat in pats):
            fails.append(f"{rid}: fixture does not contain any of its "
                         f"patterns (canary law)")
        if rule.get("tool") == "mode_lint":
            proc = subprocess.run(
                [sys.executable, str(repo / "tools/mode_lint.py"),
                 "--root", str(repo / "../xr-core")],
                capture_output=True, text=True)
            if proc.returncode != 0:
                fails.append(f"{rid}: mode_lint is red (must be green)")
            continue
        for hit in scan_scope(repo, rule):
            fails.append(hit)

    # negative fixtures must trip no pattern (no false-positive law)
    neg = repo / FIXTURES / "negative"
    for f in sorted(neg.glob("*")) if neg.is_dir() else []:
        ftext = f.read_text(encoding="utf-8", errors="replace")
        for rule in active:
            for pat in rule.get("patterns") or []:
                if pat and pat in ftext:
                    fails.append(f"negative fixture {f.name} trips "
                                 f"{rule['id']} via {pat!r}")

    # semgrep rules must exist and be well-formed
    import yaml as _yaml
    sd = repo / SEMGREP_DIR
    semgrep_files = sorted(sd.glob("*.yaml")) if sd.is_dir() else []
    if not semgrep_files:
        fails.append("no semgrep rule files")
    for sf in semgrep_files:
        try:
            sdoc = _yaml.safe_load(sf.read_text(encoding="utf-8"))
            if not sdoc or not sdoc.get("rules"):
                fails.append(f"{sf}: missing rules: list")
        except Exception as exc:  # noqa: BLE001
            fails.append(f"{sf}: unparseable ({exc})")

    for gate in doc.get("gates") or []:
        if not gate.get("ci_command"):
            fails.append(f"gate {gate.get('id')}: no ci_command")

    if args.json:
        print(json.dumps({"tool": "sast_check", "rules": len(rules),
                          "count": len(fails), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"sast_check: {len(rules)} rule(s), {len(fails)} violation(s) "
              f"({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
