#!/usr/bin/env python3
"""tools/cosmetic_scope_single_check.py — T5 exception-interplay gate.

The P12 brief, T5: "Cosmetic and network must consult the SAME P11
`exception-add`/`scopes` object; 'shields down' flips one bit both read."
This gate proves the cosmetic half of that law two ways, from artifacts:

  1. THE MATRIX FLOOR — docs/contracts/vectors/cosmetic-v1.json must carry
     >=40 `matrix-*` cases (the scope-key/identity/OOPIF matrix). A matrix
     that silently lost its rows is a gate that certifies nothing.

  2. THE FOUR LAWS, asserted as relations over the committed vector bytes,
     never as prose:
       (a) embedder-shields-down must NOT extend to a cross-site frame:
           the `matrix-scope-key-embedder-*` cases must all be refused with
           `embedder-refused` (the embedder is structurally not an input);
       (b) a frame's exception must NOT reach the embedder: two frames with
           different `frame_site` and identical identity/trust derive
           DIFFERENT keys (all six site-matrix hexes distinct), while the
           partition stays constant (identity+trust only — eviction is
           per-identity, so a site never adds itself to the partition);
       (c) same site, different identity => different key-set: for the
           identity matrix (one site, six identities, one trust) every hex
           AND every partition is distinct;
       (d) eviction for one identity never serves another: partition is
           (trust, identity)-derived, so identity A's partition can never be
           reached from identity B's key — asserted as (c)'s distinct
           partitions PLUS (b)'s site-invariance of the partition (partitions
           equal across sites for one identity, hexes differ).

  3. THE SINGLE-SCOPE-OBJECT LAW (grep-proved): the cosmetic surface
     (xr-core renderer/cosmetic/** and fakes/cosmetic.py) must contain NONE
     of the shield exception-store grammar (exception-add / exception-remove
     / exception-sweep / site-toggle / scope_id / expiry_mono /
     user-site-toggle / workspace / list_id). Cosmetic reads the SAME scopes
     object shield writes; a second, private store is a split-brain and this
     gate reddens on it. The negative (a planted private store) lives in
     tools/negatives/p12_t5.sh.

Deterministic (no clock, no network); stdlib only. Exit 0 pass · 1 fail ·
2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
VECTORS = "docs/contracts/vectors/cosmetic-v1.json"
MIN_TOTAL = 150
MIN_MATRIX = 40
# The shield exception-scope grammar (xr-core/shield/core/scope.h). The
# cosmetic surface must contain NONE of these: its exceptions are the same
# object shield writes, never a private copy.
SCOPE_STORE_TOKENS = ("exception-add", "exception-remove", "exception-sweep",
                      "site-toggle", "scope_id", "expiry_mono",
                      "user-site-toggle", "workspace", "list_id")
COSMETIC_DIRS = ("renderer/cosmetic", "fakes/cosmetic.py")


def _hex(case: dict) -> str | None:
    e = case.get("expect")
    return e.get("hex") if isinstance(e, dict) else None


def _partition(case: dict) -> str | None:
    e = case.get("expect")
    return e.get("partition") if isinstance(e, dict) else None


def _by_id(cases: list[dict], prefix: str) -> dict[str, dict]:
    return {c["id"]: c for c in cases if c["id"].startswith(prefix)}


def _distinct(vals: list[str]) -> bool:
    return len(set(vals)) == len(vals)


def check_matrix(cases: list[dict]) -> tuple[list[str], int]:
    fails: list[str] = []
    matrix = [c for c in cases if c["id"].startswith("matrix-")]
    if len(matrix) < MIN_MATRIX:
        fails.append(f"matrix floor: {len(matrix)} matrix-* cases "
                     f"(< {MIN_MATRIX} — the T5 scope-key/identity/OOPIF "
                     f"matrix is the brief's hard floor)")
    # Law (a): every NON-EMPTY embedder case is refused with the closed
    # reason; the empty/non-string embedder cases stay pinned as refusals'
    # exact complements (an empty embedder is no attempt, a non-string one is
    # not a refusal) so a behaviour change on either reddens too.
    emb = _by_id(cases, "matrix-scope-key-embedder-")
    refused = 0
    non_empty = 0
    for cid in sorted(emb):
        e = emb[cid].get("expect")
        args = emb[cid].get("args", {})
        eb = args.get("embedder_site")
        if isinstance(eb, str) and eb:
            non_empty += 1
            if not isinstance(e, dict) or e.get("reason") != "embedder-refused":
                fails.append(f"{cid}: non-empty embedder must be REFUSED "
                             f"(embedder-refused) — got {e!r}")
            elif e.get("error") == "kRejected":
                refused += 1
        else:
            if not isinstance(e, dict) or not e.get("hex"):
                fails.append(f"{cid}: empty/non-string embedder must still "
                             f"derive a key (only a real embedder is "
                             f"refused) — got {e!r}")
    if non_empty < 3 or refused != non_empty:
        fails.append("embedder-refusal matrix: fewer than 3 non-empty-embedder "
                     "refusals pinned")
    # Law (b)+(d-half): site matrix — distinct hexes, CONSTANT partition.
    # For one identity, the partition is (trust, identity) only, so all six
    # frame sites share ONE partition while each derives its own key hex.
    sites = _by_id(cases, "matrix-scope-key-site-")
    if len(sites) < 6:
        fails.append(f"site matrix: {len(sites)} cases (<6)")
    else:
        initial = [c for c in sites.values() if c["id"].endswith("-initial")]
        hexes = [h for h in (_hex(c) for c in initial) if h]
        parts = [p for p in (_partition(c) for c in initial) if p]
        if len(hexes) != len(initial):
            fails.append("site matrix: a case lost its hex — the vectors are "
                         "corrupt")
        elif not _distinct(hexes):
            fails.append("site matrix: two frame sites derived the SAME key "
                         "(a frame's exception would reach another frame)")
        if len(set(parts)) != 1:
            fails.append("site matrix: one identity must keep a CONSTANT "
                         "partition across frame sites (eviction is "
                         "per-identity; the site must never enter the "
                         "partition)")
    # Law (c)+(d): identity matrix — distinct hex AND partition per identity.
    ids = _by_id(cases, "matrix-scope-key-identity-")
    initial = [c for c in ids.values() if c["id"].endswith("-initial")]
    if len(initial) < 6:
        fails.append(f"identity matrix: {len(initial)} initial cases (<6)")
    else:
        hexes = [h for h in (_hex(c) for c in initial) if h]
        parts = [p for p in (_partition(c) for c in initial) if p]
        if not _distinct(hexes):
            fails.append("identity matrix: two identities derived the SAME "
                         "key-set on one site (cross-identity leakage)")
        if not _distinct(parts):
            fails.append("identity matrix: two identities share a partition "
                         "(eviction for one identity could serve another)")
    return fails, len(matrix)


def check_single_scope(xr_core: Path) -> list[str]:
    """Grep-prove: no shield exception-store grammar in the cosmetic surface."""
    hits: list[str] = []
    for rel in COSMETIC_DIRS:
        base = xr_core / rel
        if rel.endswith(".py"):
            files = [base] if base.is_file() else []
        else:
            files = sorted(base.rglob("*")) if base.is_dir() else []
        for p in files:
            if not p.is_file() or p.suffix not in (".py", ".cc", ".h", ".md"):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            for tok in SCOPE_STORE_TOKENS:
                if tok in text:
                    hits.append(f"{p.relative_to(xr_core)}: carries "
                                f"{tok!r}")
    if hits:
        return (["single-scope-object law: the cosmetic surface carries "
                 "shield exception-store grammar — cosmetic must consult the "
                 "SAME P11 scopes object, never a private store"] +
                [f"  {h}" for h in hits])
    return []


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="cosmetic-scope-single-check",
        description="the T5 single-scope-object + matrix-floor gate")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else \
        (repo / "../xr-core").resolve()

    try:
        doc = json.loads((repo / VECTORS).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {VECTORS}: {exc}")
        return EXIT_FAIL
    cases = doc.get("cases") or []
    if len(cases) < MIN_TOTAL:
        print(f"FAIL: {len(cases)} vectors (< {MIN_TOTAL} — the P12 floor)")
        return EXIT_FAIL

    fails, matrix_n = check_matrix(cases)
    fails += check_single_scope(xr_core)
    info = [f"matrix: {matrix_n} cases (floor {MIN_MATRIX})",
            f"vectors: {len(cases)} (floor {MIN_TOTAL})",
            f"single-scope-object: cosmetic surface carries no shield "
            f"exception-store grammar (checked "
            f"'renderer/cosmetic', 'fakes/cosmetic.py')"]
    if a.json:
        print(json.dumps({"tool": "cosmetic_scope_single_check",
                          "matrix_cases": matrix_n, "vectors": len(cases),
                          "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        for i in info:
            print(f"o  {i}")
        print(f"{'PASS' if not fails else 'FAIL'}: cosmetic_scope_single_check "
              f"({matrix_n} matrix, {len(fails)} failure(s))")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
