#!/usr/bin/env python3
"""tools/packaging_matrix_check.py — the packaging-matrix completeness gate
(P10-T4): every row of release/pkg/packaging-matrix.yaml must carry an
OWNER, a SIGNING entry (format+tool+credential), and an UPDATE-REGISTRATION
answer; every artifact glob must be non-empty; tier-2 rows must carry a
capability_statement (a demotion without a reason is a lie of omission).

Also cross-checks: every `tool:` referenced in a signing entry EXISTS in
the repo (a matrix that points at missing tooling is fiction).

Exit: 0 pass · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MATRIX = REPO / "release" / "pkg" / "packaging-matrix.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(prog="packaging-matrix-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--matrix", default=None)
    a = ap.parse_args()
    path = Path(a.matrix).resolve() if a.matrix else MATRIX
    if not path.exists():
        print(f"FAIL: matrix missing: {path}")
        return 1
    import yaml  # pinned dev dep (tools/DEPS.md)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = doc.get("rows") or []
    if not rows:
        print("FAIL: matrix has zero rows — a matrix that lists nothing "
              "certifies nothing")
        return 1
    fails: list[str] = []
    seen_os: set[str] = set()
    for row in rows:
        osname = row.get("os", "?")
        if osname in seen_os:
            fails.append(f"{osname}: duplicate row")
        seen_os.add(osname)
        for field in ("owner", "signing", "updater_registration",
                      "install_class", "artifacts", "tier"):
            if not row.get(field):
                fails.append(f"{osname}: missing required field {field!r}")
        if not isinstance(row.get("artifacts"), list) or \
                not row.get("artifacts"):
            fails.append(f"{osname}: artifacts must be a non-empty list")
        signing = row.get("signing") or {}
        for sub in ("format", "tool", "credential"):
            if not signing.get(sub):
                fails.append(f"{osname}: signing.{sub} missing")
        tool = signing.get("tool", "")
        # the tool field is "path [args...]" — existence checks the FIRST
        # token only (args are data, not paths)
        tool_path = tool.split()[0] if tool else ""
        if tool_path and tool_path != "n/a":
            if not (REPO / tool_path).exists():
                fails.append(f"{osname}: signing tool {tool!r} does not "
                             "exist in the repo (a matrix pointing at "
                             "missing tooling is fiction)")
        if row.get("tier") == 2 and not row.get("capability_statement"):
            fails.append(f"{osname}: tier-2 without a capability_statement")
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: packaging-matrix ({len(fails)} gap(s) of "
              f"{len(rows)} rows)")
        return 1
    print(f"PASS: packaging-matrix ({len(rows)} rows complete: owner + "
          "signing + update-registration + artifacts; tier-2 capability "
          "statements present; signing tools exist)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
