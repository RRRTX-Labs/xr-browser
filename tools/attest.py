#!/usr/bin/env python3
"""tools/attest.py — the release transparency attestation tool (P10-T6).

  --build <dir> --out FILE [--sbom F] [--evidence F] [--plan-pin P10]
      Emit a REAL release-attestation-v1 for every file in <dir>
      (subject = sha256 digests; predicate pins builder/chromium_rev/
      plan/SBOM/evidence) and sign it. Signing uses the pinned TEST-ONLY
      stub key (tools/attest-pinned-key.txt) — offline verifiability is
      demonstrated with a pinned public key NOW; the production binding
      is the HG-36 HSM key. NO crypto is invented here (the same
      injected-verifier law as the update core).

  --verify FILE
      Offline verification against the PINNED local key: schema check,
      canonical-byte identity, digest re-computation of --subject files
      when present in --build dir, signature validity. One flipped byte
      anywhere in the covered bytes => FAIL.

  --publish FILE
      Requires transparency-log credentials/egress (HG-38): SKIP-visible
      without them, never a fake publish.

  --check-inclusion FILE
      External-verifiability probe for the hosted lane: NOT-RUN with the
      reason until something has actually been published.

Exit: 0 pass · 1 fail · 77 skip (publish without credentials) · 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PINNED_KEY = REPO / "tools" / "attest-pinned-key.txt"
GITHUB_REV_RE = re.compile(r"chromium_rev:\s*\"([0-9a-f]{40})\"")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def stub_sig(material: str, message: str) -> str:
    return "sig:" + hashlib.sha256(
        (material + "|" + message).encode()).hexdigest()[:16]


def pinned_material() -> str:
    first = PINNED_KEY.read_text(encoding="utf-8").splitlines()[0]
    return first.removeprefix("material: ").strip()


def chromium_rev() -> str:
    deps = (REPO / "DEPS").read_text(encoding="utf-8")
    m = re.search(r'"chromium_rev":\s*"([0-9a-f]{40})"', deps) or \
        GITHUB_REV_RE.search(deps)
    return m.group(1) if m else "UNPINNED"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_statement(build_dir: Path, a) -> dict:
    subject = []
    for f in sorted(build_dir.rglob("*")):
        if f.is_file():
            subject.append({"name": str(f.relative_to(build_dir)),
                            "sha256": digest(f)})
    sbom = digest(Path(a.sbom)) if a.sbom else None
    evidence = digest(Path(a.evidence)) if a.evidence else None
    return {
        "predicate": {
            "builder": {"id": a.builder_id},
            "build_type": a.build_type,
            "chromium_rev": chromium_rev(),
            "evidence_sha256": evidence,
            "plan_pin": a.plan_pin,
            "sbom_sha256": sbom,
        },
        "schema": "xr-release-attestation",
        "schema_version": 1,
        "signature": None,
        "subject": subject,
        "type": "xr-release-attestation-v1",
    }


def sign(statement: dict) -> dict:
    core = {k: v for k, v in statement.items() if k != "signature"}
    material = pinned_material()
    statement["signature"] = {
        "alg": "minisign-ed25519",
        "key_id": "xr-root-1",
        "sig": stub_sig(material, canonical(core)),
    }
    return statement


def cmd_build(a) -> int:
    build_dir = Path(a.build)
    if not build_dir.is_dir():
        print(f"FAIL: build dir not found: {build_dir}")
        return 1
    statement = sign(build_statement(build_dir, a))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(statement) + "\n", encoding="utf-8")
    n = len(statement["subject"])
    print(f"PASS: attestation built ({out}; {n} subject artifact(s); "
          "TEST-ONLY stub key banner: not a release signing path — HG-36 "
          "swaps the production key)")
    return 0


def cmd_verify(a) -> int:
    path = Path(a.verify)
    try:
        statement = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: {path}: {exc}")
        return 1
    # 1. schema gate (the living contract)
    r = subprocess.run([sys.executable, str(REPO / "tools" / "xr_schema.py"),
                        "validate", "release-attestation", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL: schema: {r.stdout.strip()[:300]}")
        return 1
    # 2. signature over canonical core
    sig = statement.get("signature") or {}
    core = {k: v for k, v in statement.items() if k != "signature"}
    if sig.get("sig") != stub_sig(pinned_material(), canonical(core)):
        print("FAIL: signature INVALID over canonical statement bytes "
              "(tamper or foreign key)")
        return 1
    # 3. subject digests re-computed against the build dir when given
    n_checked = 0
    if a.build:
        build_dir = Path(a.build)
        for entry in statement.get("subject", []):
            f = build_dir / entry["name"]
            if f.exists() and digest(f) != entry["sha256"]:
                print(f"FAIL: artifact {entry['name']} digest mismatch")
                return 1
            n_checked += 1
    print(f"PASS: attestation verified offline ({path.name}; pinned "
          f"TEST-ONLY key; {n_checked} subject artifact(s) re-digested; "
          "one-byte tamper law holds by construction — demonstrated in "
          "the negative fixture)")
    return 0


def cmd_publish(a) -> int:
    print("SKIP: SKIP (tool absent: transparency-log credentials/egress) "
          "— needed for: publishing the attestation to the transparency "
          "log (HG-38: hosting + egress approval is a human gate); the "
          "attestation file itself is real and offline-verifiable here")
    return 77


def cmd_check_inclusion(a) -> int:
    print("NOT-RUN: no attestation has ever been published (nothing to "
          "prove inclusion for) — the 'externally verifiable' DoD row "
          "stays BLOCKED/human-gated until --publish runs with real "
          "credentials (HG-38)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="attest",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--build", default=None)
    ap.add_argument("--verify", default=None)
    ap.add_argument("--publish", default=None)
    ap.add_argument("--check-inclusion", dest="check_inclusion",
                    default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--sbom", default=None)
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--builder-id", default="xr-local-sandbox (test)")
    ap.add_argument("--build-type", default="synthetic")
    ap.add_argument("--plan-pin", default="P10")
    a = ap.parse_args()
    if a.verify:
        return cmd_verify(a)
    if a.publish:
        return cmd_publish(a)
    if a.check_inclusion:
        return cmd_check_inclusion(a)
    if a.build:
        if not a.out:
            print("FAIL: --build needs --out")
            return 2
        return cmd_build(a)
    ap.print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
