#!/usr/bin/env python3
"""tools/vendor_rust.py — the one-shot vendorer for pinned Rust crates (P11-T1).

House law: every byte enters the tree through build/upstream/fetch.py (the
chokepoint) and is VERIFIED against a sha256 that UPSTREAM itself pinned
before extraction: adblock's published .crate tarball carries the crate's own
Cargo.lock, and each [[package]] `checksum` there is the sha256 of that
.crate file — static.crates.io can serve wrong bytes but never unverified
ones (ADR-0044 allowlist ceremony). Graph resolution logic (feature-aware
build closure, license verdicts, GHSA matching) lives in
tools/vendor_rust_graph.py (touched-file size law); this file is the fetch +
write half:

  * <out>/<crate>/<version>/  — the root crate (tarball bytes verbatim) +
    MANIFEST.sha256 (per-file, upstream bytes; xr-authored files land in
    MANIFEST.xr.sha256 — written by vendor_check-verified hand, never here)
  * <out>/vendor/<name>-<ver>/ — the build closure, each with cargo's own
    .cargo-checksum.json (per-file sha256 + the lock's `package` checksum)
  * <out>/Cargo.lock — byte-identical copy of the tarball's lock
  * <out>/.cargo/config.toml — source replacement -> the vendor dir
  * <out>/supply-chain/{licenses.json,advisories.json} — the R7 substitute:
    per-crate license record (chosen branch per SPDX disjunction) + all
    reviewed GHSA rust advisories matched against the vendored set through
    the chokepoint (a hit is a red; an unparseable range is NEEDS-REVIEW,
    never a silent miss).

Dev-dep-only subtrees (criterion/reqwest/tokio/…) are NOT vendored — the
honest --offline boundary is the build graph (PROVENANCE.md records it; the
hosted lane's `cargo test` fetches dev-deps runner-side, like pip).

Usage: --plan (closure + sizes, no writes) | --vendor --as-of YYYY-MM-DD
       [--offline cached-bytes-only] [--features f1,f2].
Exit: 0 ok · 1 verification/advisory/license failure · 2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import time
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build" / "upstream"))
sys.path.insert(0, str(REPO / "tools"))
import fetch  # noqa: E402 — the chokepoint (ADR-0044)
import vendor_rust_graph as vg  # noqa: E402

ROOT_CRATE = ("adblock", "0.13.3")
ROOT_SHA256 = "f44b96a666a23c12acad7c688bfe8638a7094e7eabe765b09a6864ab991c676d"
CACHE = REPO / "work" / "upstream-cache" / "crates"
DEFAULT_OUT = REPO.parent / "xr-core" / "third_party" / "rust"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cached_get(url: str, offline: bool) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / (sha256_bytes(url.encode()) + ".bin")
    if key.is_file():
        return key.read_bytes()
    if offline:
        raise SystemExit(f"error: --offline but no cache for {url}")
    raw = fetch.http_get(url)
    key.write_bytes(raw)
    return raw


def crate_bytes(name: str, version: str, offline: bool) -> bytes:
    return cached_get(fetch.crates_io_crate_url(name, version), offline)


def tarball_files(raw: bytes, prefix: str) -> dict[str, bytes]:
    """name -> bytes for every regular file under the tarball's root dir."""
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.startswith(prefix + "/"):
                continue
            rel = m.name[len(prefix) + 1:]
            if rel:
                out[rel] = tf.extractfile(m).read()
    return out


def verified_dep(nv, lock, offline, raws) -> bytes:
    """Fetch + sha256-verify one closure crate against the lock (abort on
    mismatch: the CDN served bytes upstream never pinned)."""
    name, version = nv
    entry = lock.get(nv)
    if entry is None or not entry["checksum"]:
        raise SystemExit(f"error: {name} {version}: no registry checksum in "
                         "the crate lock — refusing unverifiable bytes")
    if nv in raws:
        return raws[nv]
    raw = crate_bytes(name, version, offline)
    got = sha256_bytes(raw)
    if got != entry["checksum"]:
        raise SystemExit(f"error: sha256 MISMATCH {name}-{version}.crate: "
                         f"lock says {entry['checksum']}, got {got} — "
                         "aborting, nothing written")
    raws[nv] = raw
    return raw


def ghsa_rust_advisories(names: set[str], offline: bool) -> list[dict]:
    """Reviewed GHSA advisories AFFECTING the vendored crate names — one
    `affects=<crate>` query per crate through the chokepoint (the bulk
    listing hits GitHub's deep-pagination cap at ~2,200 entries, and we
    only need our own set anyway). Disk-cached, so a rate-limit 403
    mid-run resumes where it stopped. Deduped by ghsa_id."""
    out: dict[str, dict] = {}
    for name in sorted(names):
        page = 1
        while True:
            url = fetch.github_api_url(
                "advisories?ecosystem=rust&type=reviewed&per_page=100"
                f"&affects={name}&page={page}")
            if not offline:
                time.sleep(1.5)  # unauthenticated-rate politeness
            batch = json.loads(cached_get(url, offline))
            for a in batch:
                out[a["ghsa_id"]] = a
            if len(batch) < 100:
                break
            page += 1
    return list(out.values())


def write_root_crate(out: Path, files: dict[str, bytes],
                     name: str, version: str) -> Path:
    root = out / name / version
    if root.exists():
        raise SystemExit(f"error: {root} exists — refusing to overwrite a "
                         "vendored pin in place (vendor a NEW version dir; "
                         "UPDATING.md)")
    manifest = {}
    for rel in sorted(files):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(files[rel])
        manifest[rel] = sha256_bytes(files[rel])
    (root / "MANIFEST.sha256").write_text(
        "".join(f"{h}  {r}\n" for r, h in sorted(manifest.items())))
    return root


def write_vendor_crate(out: Path, raw: bytes, name: str, version: str,
                       checksum: str) -> None:
    dest = out / "vendor" / f"{name}-{version}"
    files = tarball_files(raw, f"{name}-{version}")
    per_file = {}
    for rel in sorted(files):
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(files[rel])
        per_file[rel] = sha256_bytes(files[rel])
    (dest / ".cargo-checksum.json").write_text(
        json.dumps({"files": per_file, "package": checksum},
                   indent=1, sort_keys=True) + "\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vendor_rust",
                                 description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true",
                      help="compute+verify the closure, print it, write nothing")
    mode.add_argument("--vendor", action="store_true",
                      help="write the full vendored layout")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--features", default=None,
                    help="extra features beyond `default` (comma list)")
    ap.add_argument("--as-of", default=None,
                    help="date stamp for supply-chain records (--vendor "
                         "requires it; determinism: no wall clock)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.vendor and not a.as_of:
        ap.error("--vendor requires --as-of YYYY-MM-DD (no wall clock)")
    out = Path(a.out).resolve()

    raw = crate_bytes(*ROOT_CRATE, a.offline)
    got = sha256_bytes(raw)
    if got != ROOT_SHA256:
        print(f"FAIL: {ROOT_CRATE[0]}-{ROOT_CRATE[1]}.crate sha256 {got} != "
              f"pinned {ROOT_SHA256} — refusing", file=sys.stderr)
        return 1
    files = tarball_files(raw, f"{ROOT_CRATE[0]}-{ROOT_CRATE[1]}")
    lock_text = files["Cargo.lock"].decode()
    lock = vg.parse_lock(lock_text)
    root_manifest = tomllib.loads(files["Cargo.toml"].decode())
    lock_sha = sha256_bytes(lock_text.encode())

    raws: dict[tuple[str, str], bytes] = {}
    closure, manifests = vg.build_closure(
        lock, root_manifest, ROOT_CRATE,
        lambda nv: tomllib.loads(tarball_files(
            verified_dep(nv, lock, a.offline, raws),
            f"{nv[0]}-{nv[1]}")["Cargo.toml"].decode()),
        root_features={"default"} | set(
            (a.features or "").split(",") if a.features else []) - {""})

    plan = []
    for nv in sorted(closure):
        name, version = nv
        entry = lock[nv]
        lic = manifests[nv].get("package", {}).get("license")
        plan.append({"crate": name, "version": version,
                     "bytes": len(raws[nv]), "license": lic})
    total = sum(p["bytes"] for p in plan)
    bad, chosen_map = [], {}
    for p in plan:
        ok, chosen = vg.license_verdict(p["license"])
        key = p["crate"] + " " + p["version"]
        if not ok:
            bad.append(f"{key}: {p['license']}")
        else:
            chosen_map[key] = chosen
    if bad:
        print("FAIL: license expression(s) with no allowed branch — DR-04 "
              "says stop, not shrug:", file=sys.stderr)
        for b in sorted(bad):
            print(f"  {b}", file=sys.stderr)
        return 1
    if a.plan:
        if a.json:
            print(json.dumps({"root": list(ROOT_CRATE), "root_sha256": got,
                              "lock_sha256": lock_sha, "closure": plan,
                              "crate_count": len(plan),
                              "tarball_bytes": total}, indent=1))
        else:
            print(f"root: adblock {ROOT_CRATE[1]} sha256 {got[:16]}… "
                  f"lock sha256 {lock_sha[:16]}…")
            for p in plan:
                print(f"  {p['crate']} {p['version']} {p['bytes']:>9,} B "
                      f"{p['license']}")
            print(f"closure: {len(plan)} crates, {total:,} tarball bytes "
                  "(dev-dep-only subtrees excluded)")
        return 0

    if a.json:
        pass  # --vendor --json prints the summary JSON at the end
    advs = ghsa_rust_advisories({n for n, _ in closure} | {ROOT_CRATE[0]},
                                a.offline)
    matched = vg.match_advisories(closure | {ROOT_CRATE}, advs)
    if matched["hits"]:
        print("FAIL: vendored crate(s) inside a reviewed GHSA advisory range "
              "(stop-and-report):", file=sys.stderr)
        for h in matched["hits"]:
            print(f"  {h['crate']} {h['vendored_version']} — {h['ghsa_id']} "
                  f"({h['severity']}, {h['vulnerable_version_range']})",
                  file=sys.stderr)
        return 1

    write_root_crate(out, files, *ROOT_CRATE)
    for nv in sorted(closure):
        name, version = nv
        write_vendor_crate(out, raws[nv], name, version, lock[nv]["checksum"])
    (out / "Cargo.lock").write_bytes(lock_text.encode())
    cargo_dir = out / ".cargo"
    cargo_dir.mkdir(parents=True, exist_ok=True)
    (cargo_dir / "config.toml").write_text(
        "# P11-T1 vendored-source replacement (ADR-0044). Cargo discovers\n"
        "# this file from any crate dir under third_party/rust/. The lock's\n"
        "# dev-dep-only entries are intentionally NOT vendored: the honest\n"
        "# --offline boundary is the build graph (supply-chain/PROVENANCE.md).\n"
        '[source.crates-io]\nreplace-with = "xr-vendored-sources"\n\n'
        '[source.xr-vendored-sources]\ndirectory = "vendor"\n')
    sc = out / "supply-chain"
    sc.mkdir(parents=True, exist_ok=True)
    (sc / "advisories.json").write_text(json.dumps(
        {"as_of": a.as_of,
         "source": "api.github.com /advisories?ecosystem=rust&type=reviewed"
                   "&affects=<crate> (per-crate, through the fetch.py "
                   "chokepoint; bulk listing is deep-pagination-capped)",
         "advisories_scanned": len(advs), "match": matched},
        indent=1, sort_keys=True) + "\n")
    (sc / "licenses.json").write_text(json.dumps(
        {"as_of": a.as_of,
         "root": {"crate": ROOT_CRATE[0], "version": ROOT_CRATE[1],
                  "license": root_manifest["package"]["license"],
                  "sha256_crate": got, "sha256_lock": lock_sha},
         "crates": {p["crate"] + " " + p["version"]:
                    {"expression": p["license"],
                     "chosen": chosen_map.get(p["crate"] + " " + p["version"])}
                    for p in plan}}, indent=1, sort_keys=True) + "\n")
    summary = {"vendored": f"{out}", "root": list(ROOT_CRATE),
               "root_sha256": got, "lock_sha256": lock_sha,
               "crate_count": len(closure), "tarball_bytes": total,
               "advisories_scanned": len(advs),
               "advisory_hits": len(matched["hits"]),
               "needs_review": len(matched["needs_review"])}
    if a.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"vendored: adblock {ROOT_CRATE[1]} + {len(closure)} crates "
              f"({total:,} tarball bytes) -> {out}")
        print(f"advisories: {len(advs)} reviewed GHSA scanned, "
              f"{len(matched['hits'])} hits, "
              f"{len(matched['needs_review'])} NEEDS-REVIEW")
        print("NEXT: hand-write README.xr.md + UPDATING.md + PROVENANCE.md, "
              "then tools/vendor_check.py --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
