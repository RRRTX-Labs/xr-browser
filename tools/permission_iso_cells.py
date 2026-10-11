#!/usr/bin/env python3
"""tools/permission_iso_cells.py — the P15 permission-overlay isolation cells
(P15-CLOSE C8, plan T9.4, DoD 8).

Split out of tools/isolation_matrix.py by the touched-file size law (the
identity_iso_cells.py precedent). These cells drive the permission overlay's
behavioral fake (xr-core/fakes/permissions.py, byte-identical to the compiled
host on the deterministic surface — tools/permission_host_parity.py) for every
identity pair the matrix declares:

  * permissions-grant-scope: a grant made in identity A is visible in B's
    projection only when A and B are the same identity;
  * permissions-revoke-scope: revoke-all in A leaves B's grant standing (and
    takes it when A and B are the same identity);
  * permissions-deny-list: putting A on the deny list never denies B;
  * permissions-audit-attribution: every audit row an op in A emits names A,
    never B.

The overlay is keyed by the identity value (vid), not by the trust tier. The
matrix's `standard` and `shield` entries share one vid (same identity, trust
differs), so for that pair the expected answer is "shared", and the cell
passes only when the overlay shares; for every other pair it passes only when
nothing crosses. "Visibility equals identity equality" is the assertion.

Browser-mode permission cells (a revoke reaching a live tab, rows rendered on
an Activity surface) are not run here: isolation_matrix.py records them
NOT-RUN with the owning phase and the method path the matrix names, and
reddens if that path does not exist.

Standalone (the negative): `--xr-core DIR [--plant leak]`. The plant collapses
every identity onto one overlay key before each op — an overlay that ignores
identity — and the grant/revoke/deny cells must FAIL.

Stdlib only. No wall clock: `now` is a fixed millisecond constant.
Exit (standalone): 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

PERMISSION_MECHS = ("permissions-grant-scope", "permissions-revoke-scope",
                    "permissions-deny-list", "permissions-audit-attribution")
NOW = 1_790_000_000_000          # fixed ms; the overlay core reads no clock
DOMAIN = "example.com"
_LEAK_KEY = "xr:00000000-0000-4000-8000-00000000leak"


def load_fake(xr_core: Path) -> Any:
    path = xr_core / "fakes" / "permissions.py"
    if not path.is_file():
        raise RuntimeError(f"permissions fake missing at {path}")
    spec = importlib.util.spec_from_file_location("xr_permissions_fake", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class _Overlay:
    """apply() with the store threaded through; `leak` ignores identity."""

    def __init__(self, fake: Any, leak: bool) -> None:
        self.fake, self.leak = fake, leak
        self.store = fake.empty_store()
        self.rows: list[dict[str, Any]] = []

    def op(self, method: str, **args: Any) -> None:
        if self.leak and "identity" in args:
            args["identity"] = _LEAK_KEY
        err, self.store, rows = self.fake.apply(method, self.store, args, NOW)
        if err:
            raise RuntimeError(f"{method} refused: {err}")
        self.rows.extend(rows)

    def view(self) -> dict[str, Any]:
        return self.fake.project_view(self.store)

    def grants_of(self, vid: str) -> list[dict[str, Any]]:
        key = _LEAK_KEY if self.leak else vid
        return [g for g in self.view()["grants"] if g["identity"] == key]


def _grant(o: _Overlay, vid: str, cap: str = "camera") -> None:
    o.op("grant", identity=vid, domain=DOMAIN, capability=cap, scope="7d")


def _cell_grant(fake: Any, a: str, b: str, leak: bool) -> tuple[bool, str]:
    o = _Overlay(fake, leak)
    _grant(o, a)
    seen_by_b = len(o.grants_of(b)) > 0
    want = a == b
    return seen_by_b == want, (f"grant in A visible in B: {seen_by_b} "
                               f"(expected {want}{', same identity' if want else ''})")


def _cell_revoke(fake: Any, a: str, b: str, leak: bool) -> tuple[bool, str]:
    o = _Overlay(fake, leak)
    _grant(o, a, "camera")
    _grant(o, b, "microphone")
    o.op("revoke-all", identity=a)
    b_left = len(o.grants_of(b))
    want = 0 if a == b else 1
    return b_left == want, f"B grants after revoke-all in A: {b_left} (expected {want})"


def _cell_deny(fake: Any, a: str, b: str, leak: bool) -> tuple[bool, str]:
    o = _Overlay(fake, leak)
    o.op("set-denied", identity=a, denied=True)
    denied = o.view()["denied_identities"]
    b_denied = (_LEAK_KEY if leak else b) in denied
    want = a == b
    return b_denied == want, f"B on the deny list after denying A: {b_denied} (expected {want})"


def _cell_audit(fake: Any, a: str, b: str, leak: bool) -> tuple[bool, str]:
    o = _Overlay(fake, leak)
    _grant(o, a)
    o.op("set-default", identity=a, capability="geolocation", state="kDeny")
    o.op("revoke-site", identity=a, domain=DOMAIN)
    key = _LEAK_KEY if leak else a
    wrong = [r for r in o.rows if r["identity"] != key]
    ok = bool(o.rows) and not wrong
    return ok, f"{len(o.rows)} audit row(s) from A's ops; {len(wrong)} name another identity"


CELLS: dict[str, Callable[[Any, str, str, bool], tuple[bool, str]]] = {
    "permissions-grant-scope": _cell_grant,
    "permissions-revoke-scope": _cell_revoke,
    "permissions-deny-list": _cell_deny,
    "permissions-audit-attribution": _cell_audit,
}


def run_permission_cells(xr_core: Path, matrix: dict[str, Any],
                         leak: bool = False) -> list[dict[str, Any]]:
    """One cell per (fake permission mechanism x identity pair), matrix order."""
    fake = load_fake(xr_core)
    idents = {i["id"]: i for i in matrix["identities"]}
    cells: list[dict[str, Any]] = []
    for mech in matrix["mechanisms"]:
        if mech["id"] not in PERMISSION_MECHS or mech["mode"] != "fake":
            continue
        for a, b in matrix["identity_pairs"]:
            va, vb = idents[a]["vid"], idents[b]["vid"]
            try:
                ok, detail = CELLS[mech["id"]](fake, va, vb, leak)
            except RuntimeError as exc:
                ok, detail = False, f"op failed: {exc}"
            cells.append({"mechanism": mech["id"], "pair": [a, b], "mode": "fake",
                          "verdict": "PASS" if ok else "FAIL",
                          "detail": f"{a}/{b}: {detail}"})
    return cells


def method_problems(repo: Path, matrix: dict[str, Any]) -> list[str]:
    """A browser cell that names a method must name a path (and anchor) that exists."""
    out: list[str] = []
    for mech in matrix["mechanisms"]:
        m = mech.get("method")
        if not m:
            continue
        path, _, anchor = m.partition("#")
        f = repo / path
        if not f.is_file():
            out.append(f"{mech['id']}: method path {path} does not exist")
            continue
        if anchor:
            heads = {_slug(ln.lstrip("#").strip())
                     for ln in f.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("#")}
            if anchor not in heads:
                out.append(f"{mech['id']}: method anchor #{anchor} not found in {path}")
    return out


def _slug(title: str) -> str:
    s = "".join(c if c.isalnum() or c in " -_" else "" for c in title.lower())
    return s.strip().replace(" ", "-")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="permission_iso_cells")
    ap.add_argument("--xr-core", required=True)
    ap.add_argument("--matrix", default="",
                    help="default: <xr-core>/test/isolation/matrix.yaml")
    ap.add_argument("--plant", choices=["leak"], help="negative: ignore identity")
    args = ap.parse_args(argv)
    import yaml
    xr_core = Path(args.xr_core).resolve()
    mpath = Path(args.matrix) if args.matrix else xr_core / "test/isolation/matrix.yaml"
    matrix = yaml.safe_load(mpath.read_text(encoding="utf-8"))
    cells = run_permission_cells(xr_core, matrix, leak=args.plant == "leak")
    if not cells:
        print("FAIL: permission_iso_cells executed 0 cells (empty-run law)")
        return 1
    bad = [c for c in cells if c["verdict"] != "PASS"]
    for c in bad:
        print(f"FAIL: {c['mechanism']} {c['pair']}: {c['detail']}")
    print(f"{'FAIL' if bad else 'PASS'}: permission_iso_cells "
          f"({len(cells) - len(bad)}/{len(cells)} cells pass)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
