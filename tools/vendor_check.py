#!/usr/bin/env python3
"""tools/vendor_check.py — the offline verifier for the vendored Rust pin (P11-T1).

The vendorer (tools/vendor_rust.py) runs once per pin through the network
chokepoint; THIS tool runs in the gates, offline, forever after: the vendored
tree must be exactly the bytes upstream published, sealed by sha256 at every
level. What it checks (any failure is a red that names the offender):

  1. root pin dir <root>/adblock/<version>/: every file is covered by
     exactly one of MANIFEST.sha256 (upstream bytes) or MANIFEST.xr.sha256
     (xr-authored) and every recorded digest matches — a planted tamper, a
     deletion, or an unaccounted extra file is caught per-file.
  2. <root>/Cargo.lock is byte-identical to the root crate's own Cargo.lock
     and its sha256 equals the supply-chain record.
  3. every vendor/<name>-<version>/ has a cargo .cargo-checksum.json whose
     per-file digests match the tree, whose `package` checksum matches the
     Cargo.lock entry, and with no unaccounted files.
  4. CLOSURE COMPLETENESS, recomputed offline from the vendored manifests:
     the feature-aware build closure (tools/vendor_rust_graph.py) of the
     root crate must equal the vendor/ dir set — a missing dep would break
     the hosted `cargo build --offline`, and this catches it without cargo.
  5. supply-chain/: licenses.json covers every vendored crate and every
     expression has an allowed branch (DR-04); advisories.json has zero
     hits and zero NEEDS-REVIEW rows (an unresolved range is a red, not a
     shrug); PROVENANCE.md present.
  6. .cargo/config.toml performs source replacement into vendor/.

Usage: python3 tools/vendor_check.py [--root DIR] [--check] [--json]
Exit: 0 pass · 1 drift/consistency failure · 2 usage (no such tree).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import vendor_rust_graph as vg  # noqa: E402

DEFAULT_ROOT = REPO.parent / "xr-core" / "third_party" / "rust"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest_file(p: Path) -> dict[str, str]:
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise SystemExit(f"error: bad manifest line in {p}: {line!r}")
        out[parts[1]] = parts[0]
    return out


def check_root_dir(root: Path, fails: list[str]) -> tuple[Path, dict] | None:
    adirs = sorted((root / "adblock").glob("*/")) if (root / "adblock").is_dir() else []
    if len(adirs) != 1:
        fails.append(f"root pin dir: expected exactly one adblock/<version>/ "
                     f"under {root}, found {len(adirs)}")
        return None
    pin = adirs[0]
    recorded: dict[str, str] = {}
    for mname in ("MANIFEST.sha256", "MANIFEST.xr.sha256"):
        mp = pin / mname
        if not mp.is_file():
            fails.append(f"root pin dir: missing {mname}")
            return None
        for rel, h in parse_manifest_file(mp).items():
            if rel in recorded:
                fails.append(f"root pin dir: {rel} listed in BOTH manifests")
            recorded[rel] = h
    on_disk = {p.relative_to(pin).as_posix()
               for p in pin.rglob("*") if p.is_file()}
    unaccounted = sorted(on_disk - set(recorded) -
                         {"MANIFEST.sha256", "MANIFEST.xr.sha256"})
    for rel in unaccounted:
        fails.append(f"root pin dir: unaccounted file {rel} (in no manifest)")
    for rel in sorted(set(recorded) - on_disk):
        fails.append(f"root pin dir: manifest lists MISSING file {rel}")
    for rel in sorted(set(recorded) & on_disk):
        got = sha256_file(pin / rel)
        if got != recorded[rel]:
            fails.append(f"root pin dir: TAMPER/DRIFT {rel}: manifest "
                         f"{recorded[rel][:12]}… != tree {got[:12]}…")
    man = tomllib.loads((pin / "Cargo.toml").read_text(encoding="utf-8")) if (pin / "Cargo.toml").is_file() else {}
    return pin, man


def check_lock(root: Path, pin: Path, fails: list[str]) -> dict | None:
    outer, inner = root / "Cargo.lock", pin / "Cargo.lock"
    if not outer.is_file() or not inner.is_file():
        fails.append("Cargo.lock: missing outer or root-crate copy")
        return None
    if outer.read_bytes() != inner.read_bytes():
        fails.append("Cargo.lock: outer copy is NOT byte-identical to the "
                     "tarball's own lock")
    lic_path = root / "supply-chain" / "licenses.json"
    if lic_path.is_file():
        lic = json.loads(lic_path.read_text(encoding="utf-8"))
        want = lic.get("root", {}).get("sha256_lock")
        got = sha256_file(inner)
        if want and want != got:
            fails.append(f"Cargo.lock: sha256 {got[:12]}… != supply-chain "
                         f"record {want[:12]}…")
    return vg.parse_lock(inner.read_text(encoding="utf-8"))


def check_vendor_dir(root: Path, lock: dict, fails: list[str]) -> set:
    vdir = root / "vendor"
    vendored = set()
    if not vdir.is_dir():
        fails.append("vendor/: missing")
        return vendored
    for crate_dir in sorted(p for p in vdir.iterdir() if p.is_dir()):
        name, _, version = crate_dir.name.rpartition("-")
        nv = (name, version)
        vendored.add(nv)
        cs = crate_dir / ".cargo-checksum.json"
        if not cs.is_file():
            fails.append(f"vendor/{crate_dir.name}: no .cargo-checksum.json")
            continue
        rec = json.loads(cs.read_text(encoding="utf-8"))
        entry = lock.get(nv)
        if entry is None:
            fails.append(f"vendor/{crate_dir.name}: not a registry package "
                         "in Cargo.lock — unaccounted crate")
        elif rec.get("package") != entry["checksum"]:
            fails.append(f"vendor/{crate_dir.name}: package checksum "
                         f"{str(rec.get('package'))[:12]}… != lock "
                         f"{str(entry['checksum'])[:12]}…")
        files = rec.get("files", {})
        on_disk = {p.relative_to(crate_dir).as_posix()
                   for p in crate_dir.rglob("*") if p.is_file()}
        on_disk.discard(".cargo-checksum.json")
        for rel in sorted(on_disk - set(files)):
            fails.append(f"vendor/{crate_dir.name}: unaccounted file {rel}")
        for rel in sorted(set(files) - on_disk):
            fails.append(f"vendor/{crate_dir.name}: MISSING file {rel}")
        for rel in sorted(set(files) & on_disk):
            got = sha256_file(crate_dir / rel)
            if got != files[rel]:
                fails.append(f"vendor/{crate_dir.name}: TAMPER/DRIFT {rel}")
    return vendored


def check_closure(root: Path, pin: Path, root_manifest: dict, lock: dict,
                  vendored: set, fails: list[str]) -> None:
    """Recompute the build closure OFFLINE from the vendored manifests."""
    name = root_manifest.get("package", {}).get("name", "adblock")
    version = root_manifest.get("package", {}).get("version", "0.0.0")

    def load(nv):
        p = root / "vendor" / f"{nv[0]}-{nv[1]}" / "Cargo.toml"
        if not p.is_file():
            raise SystemExit(f"error: closure needs {nv[0]} {nv[1]} but "
                             f"{p} is absent — vendor/ incomplete")
        return tomllib.loads(p.read_text(encoding="utf-8"))

    try:
        closure, _ = vg.build_closure(lock, root_manifest, (name, version),
                                      load)
    except SystemExit as exc:
        fails.append(f"closure: {exc}")
        return
    missing = sorted(closure - vendored)
    extra = sorted(vendored - closure)
    for nv in missing:
        fails.append(f"closure: {nv[0]} {nv[1]} is REQUIRED by the build "
                     "graph but not vendored (cargo build --offline breaks)")
    for nv in extra:
        fails.append(f"closure: {nv[0]} {nv[1]} is vendored but not in the "
                     "recomputed build closure (unaccounted crate)")


def check_supply_chain(root: Path, vendored: set, fails: list[str]) -> None:
    sc = root / "supply-chain"
    for f in ("PROVENANCE.md", "licenses.json", "advisories.json"):
        if not (sc / f).is_file():
            fails.append(f"supply-chain/: missing {f}")
    lp, ap = sc / "licenses.json", sc / "advisories.json"
    if lp.is_file():
        lic = json.loads(lp.read_text(encoding="utf-8"))
        covered = lic.get("crates", {})
        for nv in sorted(vendored):
            key = f"{nv[0]} {nv[1]}"
            if key not in covered:
                fails.append(f"licenses.json: no record for vendored {key}")
            else:
                ok, _ = vg.license_verdict(covered[key].get("expression"))
                if not ok:
                    fails.append(f"licenses.json: {key} expression "
                                 f"{covered[key].get('expression')!r} has no "
                                 "allowed branch (DR-04)")
    if ap.is_file():
        adv = json.loads(ap.read_text(encoding="utf-8"))
        m = adv.get("match", {})
        for h in m.get("hits", []):
            fails.append(f"advisories.json: HIT {h['crate']} "
                         f"{h['vendored_version']} in {h['ghsa_id']} "
                         f"({h['vulnerable_version_range']}) — STOP")
        for r in m.get("needs_review", []):
            fails.append(f"advisories.json: NEEDS-REVIEW {r['crate']} "
                         f"{r['vendored_version']} range "
                         f"{r['vulnerable_version_range']!r} unparseable — "
                         "resolve it, never a silent miss")


def check_config(root: Path, fails: list[str]) -> None:
    cfg = root / ".cargo" / "config.toml"
    if not cfg.is_file():
        fails.append(".cargo/config.toml: missing")
        return
    text = cfg.read_text(encoding="utf-8")
    if "replace-with" not in text or 'directory = "vendor"' not in text:
        fails.append(".cargo/config.toml: does not perform source "
                     "replacement into vendor/")


def run(root: Path, as_json: bool) -> int:
    fails: list[str] = []
    if not root.is_dir():
        print(f"error: no vendored-rust tree at {root}", file=sys.stderr)
        return 2
    checked = pin = None
    got = check_root_dir(root, fails)
    if got:
        pin, root_manifest = got
        lock = check_lock(root, pin, fails)
        if lock:
            vendored = check_vendor_dir(root, lock, fails)
            check_closure(root, pin, root_manifest, lock, vendored, fails)
            check_supply_chain(root, vendored, fails)
            check_config(root, fails)
            checked = {"crates": len(vendored),
                       "files_root": len(list(pin.rglob('*')))}
    if as_json:
        print(json.dumps({"root": str(root), "fails": fails,
                          "status": "fail" if fails else "pass",
                          **(checked or {})}, indent=1))
    else:
        for f in fails:
            print(f"  FAIL: {f}")
        if fails:
            print(f"FAIL: vendor_check ({len(fails)} finding(s)) — the "
                  "vendored tree is not the tree upstream published")
        else:
            print(f"PASS: vendor_check ({checked['crates']} vendored crates "
                  "verified against the lock; root pin sealed per-file; "
                  "closure complete offline; licenses + advisories clean)")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vendor_check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--check", action="store_true",
                    help="the house verb (default behavior)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return run(Path(a.root).resolve(), a.json)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
