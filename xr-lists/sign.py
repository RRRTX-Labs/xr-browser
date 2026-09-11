#!/usr/bin/env python3
"""xr-lists/sign.py — produce the frozen list-bundle-manifest-v1 and its
detached signature (P11-T3). TEST-ONLY CHANNELS ONLY — the release path
stays HG-36/37 (HSM), exactly like build/signing/sign_artifact.py's
release-channel refusal.

NO NEW signature or rollback mechanism (§arch 3 / DoD 5):
  * the manifest is the FROZEN list-bundle-manifest-v1 document
    (docs/contracts/list-bundle-manifest-v1.schema.json — consumed
    untouched; tools/list_bundle_check.py pins its sha256);
  * the detached signature rides P10's mechanisms: the real in-sandbox
    round-trip uses gpg through build/signing/linux_repo_sign.py (the
    P10 linux-repo pattern: runtime keyring, never committed keys), and
    the artifact-channel minisign path delegates to build/signing/
    sign_artifact.py (channel dev; absent binary => visible SKIP 77);
  * client-side verification reuses xr-core/update/core (verify_policy,
    epoch, seen, backoff — pinned keys, epoch for rotation/revocation,
    seen for replay, monotonic version, LKG fallback). This tool signs;
    it does not invent a verifier.

Subcommands:
  manifest — build manifest.json ONLY (deterministic, no external tools;
             this is what the byte-law goldens pin)
  sign     — manifest + gpg detached signature (manifest.json.asc) +
             sha256sums.txt; gpg absent => 77 with a visible SKIP
  verify   — gpg-verify a detached signature; absent => 77
  minisign — the sign_artifact.py dev-channel artifact; binary absent
             => 77 (P10's minisign-on-CI pattern)

Determinism: created_epoch is a REQUIRED argument (no wall clock); same
inputs => same manifest bytes (canonical JSON, sorted keys).
Exit: 0 ok · 1 failure/refusal · 2 usage · 77 tool-absent SKIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bundle_bytes import canonical, list_sha  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
LINUX_REPO_SIGN = REPO / "build" / "signing" / "linux_repo_sign.py"
SIGN_ARTIFACT = REPO / "build" / "signing" / "sign_artifact.py"


def build_manifest(bundle: dict, bundle_id: str, epoch: int,
                   key_pin: list[str], lkg: str | None) -> dict:
    """The frozen-schema manifest: required schema_version/bundle_id/
    created_epoch/lists/key_pin; optional last_known_good_bundle_id;
    NO other top-level keys (additionalProperties:false is frozen)."""
    lists = []
    for lst in bundle["lists"]:
        lists.append({"attribution": lst["attribution"], "name": lst["name"],
                      "rules": len(lst["rules"]), "sha256": list_sha(lst)})
    man: dict = {"bundle_id": bundle_id, "created_epoch": epoch,
                 "key_pin": key_pin, "lists": lists, "schema_version": 1}
    if lkg is not None:
        man["last_known_good_bundle_id"] = lkg
    return man


def check_bundle_shape(bundle: dict) -> str | None:
    if bundle.get("schema") != "xr-list-bundle" or \
            bundle.get("schema_version") != 1:
        return "bundle-wrong-schema"
    if not isinstance(bundle.get("lists"), list):
        return "bundle-lists-not-array"
    for lst in bundle["lists"]:
        for key in ("name", "attribution", "rules"):
            if key not in lst:
                return f"bundle-list-missing:{key}"
    return None


def run_signing_tool(args: list[str], what: str) -> int:
    r = subprocess.run([sys.executable, *args], capture_output=True,
                       text=True)
    if r.returncode == 77:
        print(f"SKIP: SKIP (tool absent: gpg) — needed for: {what}; "
              "local hint: apt-get install gnupg")
        return 77
    if r.returncode != 0:
        print(f"FAIL: {what}: {r.stdout.strip()}{r.stderr.strip()}")
        return 1
    print(f"ok: {what}")
    return 0


def cmd_manifest(a, bundle: dict) -> int:
    bad = check_bundle_shape(bundle)
    if bad:
        print(f"FAIL: {bad}")
        return 1
    pins = [p for p in a.key_pin.split(",") if p]
    if not pins or any(" " in p for p in pins):
        print("FAIL: --key-pin must be a comma-separated list of "
              "non-empty tokens (shape '<alg>:<key-id>')")
        return 1
    man = build_manifest(bundle, a.bundle_id, a.epoch, pins, a.lkg)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(man) + "\n", encoding="utf-8")
    print(f"wrote manifest -> {out} ({len(man['lists'])} entries, "
          f"epoch {man['created_epoch']}, key_pin {man['key_pin']})")
    return 0


def cmd_sign(a, bundle: dict) -> int:
    rc = cmd_manifest(a, bundle)
    if rc != 0:
        return rc
    if not LINUX_REPO_SIGN.exists():
        print(f"FAIL: signing channel missing: {LINUX_REPO_SIGN}")
        return 2
    gh = Path(a.gnupghome)
    if not (gh / "private-keys-v1.d").exists() and \
            not (gh / "signing-pub.asc").exists():
        rc = run_signing_tool(
            [str(LINUX_REPO_SIGN), "keygen", "--gnupghome", str(gh)],
            "runtime gpg keygen (TEST keyring, never committed)")
        if rc != 0:
            return rc
    rc = run_signing_tool(
        [str(LINUX_REPO_SIGN), "sign", "--gnupghome", str(gh), "--in",
         str(Path(a.out)), "--mode", "detach"],
        f"detached gpg signature -> {Path(a.out).name}.asc")
    if rc != 0:
        return rc
    sums = Path(a.out).parent / "sha256sums.txt"
    lines = []
    for f in (Path(a.bundle), Path(a.out)):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        lines.append(f"{h}  {f.name}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {sums}")
    return 0


def cmd_verify(a) -> int:
    man = Path(a.manifest)
    sig = Path(a.sig) if a.sig else man.with_name(man.name + ".asc")
    if not man.exists() or not sig.exists():
        print(f"FAIL: missing {'manifest' if not man.exists() else 'signature'}")
        return 2
    return run_signing_tool(
        [str(LINUX_REPO_SIGN), "verify", "--gnupghome", str(Path(a.gnupghome)),
         "--in", str(man), "--sig", str(sig)],
        f"gpg detached verify ({man.name} vs {sig.name})")


def cmd_minisign(a) -> int:
    if shutil.which("minisign") is None:
        print("SKIP: SKIP (tool absent: minisign) — needed for: the "
              "sign_artifact.py dev-channel artifact signature (P10's "
              "minisign-on-CI pattern; real execution = hosted lane); "
              "local hint: apt-get install minisign")
        return 77
    r = subprocess.run(
        [sys.executable, str(SIGN_ARTIFACT), "--artifact", str(Path(a.manifest)),
         "--channel", "dev", "--os", "linux", "--key", a.key,
         "--out", a.out_dir], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL: sign_artifact: {r.stdout.strip()}{r.stderr.strip()}")
        return 1
    print("ok: minisign dev-channel artifact")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="xr-lists/sign.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("manifest", "sign"):
        p = sub.add_parser(name)
        p.add_argument("--bundle", required=True)
        p.add_argument("--bundle-id", required=True)
        p.add_argument("--epoch", required=True, type=int)
        p.add_argument("--key-pin", required=True,
                       help="comma-separated '<alg>:<key-id>' tokens")
        p.add_argument("--lkg", default=None)
        p.add_argument("--out", required=True)
        if name == "sign":
            p.add_argument("--gnupghome", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--manifest", required=True)
    v.add_argument("--sig", default=None)
    v.add_argument("--gnupghome", required=True)
    m = sub.add_parser("minisign")
    m.add_argument("--manifest", required=True)
    m.add_argument("--key", required=True)
    m.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if a.cmd == "verify":
        return cmd_verify(a)
    if a.cmd == "minisign":
        return cmd_minisign(a)
    bundle_path = Path(a.bundle)
    if not bundle_path.exists():
        print(f"FAIL: bundle not found: {bundle_path}")
        return 2
    if a.epoch < 0:
        print("FAIL: --epoch must be >= 0 (determinism: no wall clock)")
        return 2
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if a.cmd == "manifest":
        return cmd_manifest(a, bundle)
    return cmd_sign(a, bundle)


if __name__ == "__main__":
    sys.exit(main())
