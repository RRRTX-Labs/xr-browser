#!/usr/bin/env python3
"""tools/sibling_pin_check.py — the cross-repo pin gate (P13-C-P0.2).

THE DEFECT CLASS
----------------
A verdict computed from a sibling checkout is meaningless unless the sibling is
at the pin. Measured at e503f9e, `tools/coverage_check.py:31` resolved
`../xr-core` by layout guess and then `import commands` from it. Three outcomes,
all of them wrong:

  * sibling ABSENT   -> `ModuleNotFoundError: No module named 'commands'` — reads
                        as a broken environment, so an agent re-runs it and
                        moves on;
  * sibling OLDER    -> a VACUOUS PASS. This is the one that shipped: the
                        P13-T1 predecessor's local `../xr-core` predated the
                        panel files, so the "landed surface" scan found nothing
                        to bite and every local run was green while the hosted
                        run was red;
  * sibling DIRTY    -> HEAD agrees with the pin while the files on disk are
                        something else; the pin proves nothing.

WHAT THIS TOOL DOES
-------------------
`tools/xr_sibling.py` is the ONE resolver (no second copy of the path logic).
This tool is its gate, in two halves:

  1. PROVE — `xr_sibling.check()` against the repo: sibling present, HEAD ==
     `DEPS.xr_core_rev`, worktree clean. Failure is typed and exits 2
     (`BLOCKED-LAYOUT` / `STALE-SIBLING` / `DIRTY-SIBLING`) so the lane that
     follows never renders a verdict it cannot source.

  2. AUDIT — every file in the tree that resolves a sibling path is classified,
     because the class grows back the moment a new tool guesses. The register
     below is the enumeration, and an UNCLASSIFIED file with a resolution
     pattern is a FAILURE, not a warning: a new sibling reader must be routed or
     classified deliberately, never discovered by accident.

Classes (each entry carries its reason in the register):

  routed       resolves through `tools/xr_sibling.py` (the fix, applied)
  gate-ordered reads the sibling only AFTER this lane in tools/run_checks.sh —
               this tool verifies the ORDER in that file, so the claim is
               checked, not asserted
  arg-only     takes an explicit `--xr-core`/`--core`/`--grdp` path: the caller
               names the tree, so a nonstandard layout is a flag, not a skip
               (and the gate still proves the pin first)
  probe        live-network probe (build/upstream/*, build/sync.py): it CLONES or
               fetches the sibling itself and pins it by checkout
  test         test code: pytest runs it in this checkout, after the pin lane
  self         the resolver and the delegating utility — they ARE the pin law

Docs: docs/process/cross-repo-pin.md. Negatives: tools/negatives/p13_c02.sh
(stale sibling names both SHAs; absent sibling is BLOCKED-LAYOUT exit 2; a
routed tool that ignores the assertion is red).

Exit: 0 pass · 1 audit failure · 2 BLOCKED-SIBLING / usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xr_sibling  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# Resolution shapes actually present in this tree (the grep is in the phase
# report verbatim). P1/P3/P5 are the DEFECT (a layout guess); P2 is the same
# guess with a resolve(); P4 is an explicit path argument.
PATTERNS = {
    "P1-layout-guess": re.compile(r'parents\[\d\]\.parent\s*/\s*"xr-core"'),
    "P2-resolve-guess": re.compile(r'\.\./xr-core"\)\.resolve\(\)'),
    "P3-repo-parent": re.compile(r'\b(root|repo|REPO)\.parent\s*/\s*"xr-core"'),
    "P4-explicit-arg": re.compile(r'default="[^"]*xr-core'),
    "P5-nested-parent": re.compile(r'parent\.parent(?:\.parent)?\s*/\s*"xr-core"'),
    # P6 — the SHELL shape, missed by the first sweep and found by building on
    # the law it protects: build/webui/panel-tests.sh resolved the sibling as
    # `${XR_CORE:-$(cd "$REPO/.." && pwd)/xr-core}`, i.e. a layout guess spelled
    # in shell. The sweep had looked at .py, .sh, .mjs, .yml — the gap was the
    # PATTERN, not the extension: five regexes written from Python examples did
    # not describe the one language the panel lane is written in.
    "P6-shell-subshell-parent": re.compile(r'\(cd\s+\S*\s*\.\.[^)]*\)\s*/\s*xr-core'),
}
GUESSES = ("P1-layout-guess", "P2-resolve-guess", "P3-repo-parent",
           "P5-nested-parent", "P6-shell-subshell-parent")

# The register. Keys are repo-relative paths; values are (class, reason).
# Generated from the P13-C-P0.2 audit scan of this tree; the audit FAILS on any
# file with a resolution pattern that is missing here.
REGISTER: dict[str, tuple[str, str]] = {
    "tools/xr_sibling.py": ("self", "the resolver and the pin law"),
    "tools/sibling_pin_check.py": ("self", "this audit: pattern P6 is a string in it, so it matches itself"),
    "build/qa/_common.py": ("self", "xr_core_root() delegates to xr_sibling.check()"),
    "tools/coverage_check.py": ("routed", "roster read; the P13-C-P0.1 defect"),
    "build/webui/panel-tests.sh": ("routed", "P6 shell layout guess -> the xr_sibling CLI (P13-C-P0.2b)"),
    "build/webui/repro-check.sh": ("routed", "P6 shell layout guess -> the xr_sibling CLI (P13-C-P0.2b)"),
    "build/webui/toolchain.sh": ("routed", "P6 shell layout guess -> the xr_sibling CLI (P13-C-P0.2b)"),
    "tools/a11y_lint.py": ("routed", "P1 layout guess -> resolve_or_exit"),
    "tools/csp_lint.py": ("routed", "P1 layout guess -> resolve_or_exit"),
    "tools/descriptors_to_docs.py": ("routed", "P1 layout guess -> resolve_or_exit"),
    "tools/menu_model_check.py": ("routed", "P1 layout guess -> resolve_or_exit"),
    "tools/rtl_lint.py": ("routed", "P1 layout guess -> resolve_or_exit"),
    "tools/blink_guard_lint.py": ("routed", "P2 resolve guess -> _sibling_of()"),
    "tools/cosmetic_generic_set_check.py": ("routed", "P2 resolve guess -> _sibling_of()"),
    "tools/cosmetic_scope_single_check.py": ("routed", "P2 resolve guess -> _sibling_of()"),
    "tools/scriptlet_registry_check.py": ("routed", "P2 resolve guess -> _sibling_of()"),
    "tools/host_protocol_check.py": ("gate-ordered", "scans xr-core/*/host/*.cc; runs after this lane"),
    "tools/patch_manifest_check.py": ("arg-only", "explicit --xr-core path"),
    "tools/no_new_crypto_check.py": ("gate-ordered", "scans xr-core core/** after this lane"),
    "tools/shield_parity.py": ("arg-only", "explicit --core path (CI passes the pinned checkout)"),
    "tools/shield_state_check.py": ("gate-ordered", "reads xr-core shield/ + roster after this lane"),
    "tools/parity_completeness.py": ("gate-ordered", "parity matrix read after this lane"),
    "tools/attention_check.py": ("gate-ordered", "reads xr-core ui/ copy after this lane"),
    "tools/contracts_manifest.py": ("gate-ordered", "verifies core: paths after this lane"),
    "tools/panel_bench.py": ("gate-ordered", "bundles xr-core ui/panel after this lane"),
    "tools/about_state_check.py": ("gate-ordered", "reads xr-core update/ui before-after this lane"),
    "tools/ci_lane_discovery.py": ("gate-ordered", "discovers xr-core test Makefiles after this lane"),
    "tools/mutation_freshness.py": ("gate-ordered", "mutation targets in xr-core after this lane"),
    "tools/cosmetic_bench.py": ("gate-ordered", "cosmetic host bench after this lane"),
    "tools/differential_fuzz.py": ("gate-ordered", "fuzz fleet targets after this lane"),
    "tools/kill_matrix.py": ("gate-ordered", "host binaries built from xr-core after this lane"),
    "tools/isolation_matrix.py": ("arg-only", "writes into the sibling; path is explicit"),
    "tools/vendor_check.py": ("arg-only", "third_party/rust root is explicit"),
    "tools/vendor_rust.py": ("arg-only", "writes the vendor graph; path is explicit"),
    "tools/core_hygiene_check.py": ("arg-only", "explicit --xr-core"),
    "tools/grdp_check.py": ("arg-only", "explicit --grdp/--xr-core"),
    "tools/l10n_extract.py": ("arg-only", "explicit --xr-core/--grdp"),
    "tools/help_deep_link.py": ("arg-only", "explicit --xr-core"),
    "tools/mutation_test.py": ("arg-only", "explicit target tree"),
    "tools/secret_scan.py": ("arg-only", "explicit scan roots"),
    "build/upstream/rebase_bot.py": ("probe", "clones/checkouts the pinned sibling itself"),
    "build/upstream/fork_health.py": ("probe", "live fork probe"),
    "build/upstream/promotion.py": ("probe", "reads the pinned sibling's manifest"),
    "build/upstream/retirements.py": ("probe", "reads the pinned sibling's manifest"),
    "build/qa/perf/shield_bench.py": ("gate-ordered", "bench rig after this lane"),
    "build/spike/genpatch.py": ("arg-only", "explicit --xr-core"),
    "build/spike/spike.py": ("arg-only", "explicit --xr-core"),
    "build/webui/patch_roundtrip.py": ("arg-only", "explicit --xr-core"),
    "build/webui/cosmetic_seam_roundtrip.py": ("arg-only", "explicit --xr-core"),
    "build/webui/shield_seam_roundtrip.py": ("arg-only", "explicit --xr-core"),
    "tools/negatives/p13_c02.sh": ("test", "fixture: PLANTS an unclassified sibling reader in a scratch tree (case 4) — the pattern in this file is the defect being reproduced, which is why the audit classified it the moment it landed"),
    "tools/negatives/p11_t5.sh": ("test", "fixture: builds a scratch sibling"),
    "tools/negatives/p11_t6.sh": ("test", "fixture: builds a scratch sibling"),
}

# Directory rules for the bulk of the audit (test code + workflow clones).
DIR_RULES: tuple[tuple[str, str, str], ...] = (
    ("tools/tests/", "test", "pytest code; runs after the pin lane in this checkout"),
    ("docs/contracts/tests/", "test", "contract vectors; pytest"),
    (".github/workflows/", "workflow", "the workflow clones + checks out the DEPS pin itself"),
    ("build/tests/", "test", "build-system tests; pytest"),
    ("build/upstream/tests/", "test", "upstream kit tests; pytest"),
)
SCAN_ROOTS = ("tools", "build", "release", "scripts", ".github")
SCAN_EXTS = (".py", ".sh", ".mjs", ".yml", ".yaml")


def scan(repo: Path) -> dict[str, list[str]]:
    """{relpath: [pattern names]} for every file resolving a sibling path."""
    hits: dict[str, list[str]] = {}
    for root_name in SCAN_ROOTS:
        root = repo / root_name
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix not in SCAN_EXTS:
                continue
            rel = f.relative_to(repo).as_posix()
            try:
                src = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            found = [name for name, rx in PATTERNS.items() if rx.search(src)]
            if found:
                hits[rel] = found
    return hits


def classify(rel: str) -> tuple[str, str] | None:
    if rel in REGISTER:
        return REGISTER[rel]
    for prefix, cls, reason in DIR_RULES:
        if rel.startswith(prefix):
            return (cls, reason)
    return None


def audit(repo: Path) -> list[str]:
    """Findings for unclassified / misclassified sibling readers."""
    fails: list[str] = []
    for rel, found in sorted(scan(repo).items()):
        cls = classify(rel)
        if cls is None:
            fails.append(
                f"{rel} resolves an xr-core sibling ({', '.join(found)}) and is "
                f"NOT in the register — route it through tools/xr_sibling.py "
                f"(resolve_or_exit) or classify it with a reason here; a new "
                f"sibling reader may not land silently (P13-C-P0.2)")
            continue
        name, reason = cls
        if not reason:
            fails.append(f"{rel}: register entry has no reason")
    # A `routed` entry is a CLAIM ABOUT A FIX, so it is checked for every entry
    # in the register — not only for files that still show a resolution pattern.
    # (A correctly routed file no longer matches any pattern, which is why the
    # scan alone would never check the very entries that matter most.)
    for rel, (name, _reason) in sorted(REGISTER.items()):
        if name != "routed":
            continue
        path = repo / rel
        if not path.is_file():
            fails.append(f"{rel} is registered `routed` but does not exist")
            continue
        src = path.read_text(encoding="utf-8")
        if ("from xr_sibling import" not in src and "import xr_sibling" not in src
                and "_sibling_of(" not in src
                # a SHELL caller routes through the CLI, which is the same one
                # resolver reached the only way a shell can reach it
                and "tools/xr_sibling.py" not in src):
            fails.append(
                f"{rel} is registered `routed` but does not import "
                f"tools/xr_sibling.py — the register would be a claim about a "
                f"fix that is not there")
    return fails


def order_findings(repo: Path) -> list[str]:
    """The `gate-ordered` claim, checked: this lane must run BEFORE the lanes
    that consume the sibling. A claim about ordering that nothing verifies is
    how a gate silently loses its precondition."""
    rc = repo / "tools" / "run_checks.sh"
    if not rc.is_file():
        return [f"no tools/run_checks.sh at {repo} — cannot verify the ordering claim"]
    lines = rc.read_text(encoding="utf-8").splitlines()
    mine = [i for i, ln in enumerate(lines)
            if "sibling_pin_check" in ln or "p13_sibling_pin" in ln]
    if not mine:
        return ["tools/run_checks.sh does not call the pin lane "
                "(tools/sibling_pin_check.py, as p13_sibling_pin) — the "
                "gate-ordered class has no gate to be ordered by"]
    first = mine[0]
    fails: list[str] = []
    for tool, (cls, _why) in sorted(REGISTER.items()):
        if cls != "gate-ordered":
            continue
        stem = Path(tool).name
        uses = [i for i, ln in enumerate(lines) if stem in ln]
        if uses and min(uses) < first:
            fails.append(f"{tool} is registered `gate-ordered` but run_checks.sh "
                         f"uses it at line {min(uses) + 1}, BEFORE the pin lane "
                         f"at line {first + 1}")
    return fails


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sibling_pin_check", description=__doc__)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None,
                    help="sibling path (default: ../xr-core). An override is "
                         "NOT an exemption: every check still applies")
    ap.add_argument("--audit-only", action="store_true",
                    help="classify sibling readers without proving the pin")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()

    fails: list[str] = []
    if not args.audit_only:
        try:
            sib = xr_sibling.check(repo, override=args.xr_core)
        except xr_sibling.SiblingError as err:
            print(f"sibling_pin_check: {xr_sibling.format_error(err)}",
                  file=sys.stderr)
            return EXIT_USAGE
        print(f"pin: xr-core {sib.head} == DEPS {sib.pin} (clean worktree)")

    fails.extend(audit(repo))
    fails.extend(order_findings(repo))
    classes: dict[str, int] = {}
    for rel in scan(repo):
        cls = classify(rel)
        if cls:
            classes[cls[0]] = classes.get(cls[0], 0) + 1

    if args.json:
        print(json.dumps({"tool": "sibling_pin_check", "repo": str(repo),
                          "classes": classes,
                          "status": "pass" if not fails else "fail",
                          "failures": fails}, indent=1))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: sibling_pin_check "
              f"({sum(classes.values())} sibling reader(s) classified"
              + (", " + ", ".join(f"{k}={v}" for k, v in sorted(classes.items()))
                 if classes else "") + ")")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
