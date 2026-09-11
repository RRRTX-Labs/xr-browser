#!/usr/bin/env python3
"""tools/no_new_crypto_check.py — ONE copy of a public algorithm, never a new one.

P11-T0-b (DR-11/no-custom-crypto as interpreted by ADR-0043). Before this
gate, xr-core carried FIVE byte-identical copies of an in-house SHA-256 and
five of the JSON parser; exactly one copy was pinned by a test. A security
primitive with four unpinned copies drifts, and nobody owns it. P11 is the
phase that would add copies 6 and 7 (rule hashing, bundle digests, corpus
fingerprints), so the rule is now a gate:

SCOPE  xr-core/<x>/core/**/*.{h,cc} (every core, common included) and
       xr-core/shield/**/*.{h,cc,rs} (the network-path code, born scanned).
       The vendored third_party/ tree is NOT scanned here — it is covered by
       tools/vendor_check.py (per-file sha256) + the supply-chain records,
       and re-implementing vendored bytes is what those gates forbid.

RULES  (string literals and comments are stripped before matching, so an
       alg-id like "minisign-ed25519" in a format check is not an
       implementation; the scan is a grep+shape heuristic and says so)
  0. single-copy multiplicity: exactly ONE sha256.cc, ONE json.cc and ONE
     json_parse.cc may exist under xr-core (outside build dirs), each in
     common/core/ — the DoD's `find` proof, machine-run;
  1. algorithm constants (SHA-256 H/K, SHA-1, MD5 init vectors) outside the
     allowlisted implementation FAIL — a renamed re-copy still carries them;
  2. crypto library includes (openssl/boringssl/sodium/mbedtls/botan/
     cryptopp) FAIL anywhere in scope;
  3. banned primitive symbols (Sha1/Sha512/Sha3/Md5/Blake2/Blake3/Keccak/
     Hmac*/Pbkdf2/Hkdf/Scrypt/Argon2/Poly1305/ChaCha/Aes*/Ed25519/X25519/
     Rsa* + the crypto_sign/ge_p3/sc_reduce implementation shapes) FAIL —
     no second algorithm may appear at all; if a real need exists, that is
     a stop-and-report (P11 failure condition 4), not an edit here;
  4. PRNG: std::mt19937 / std::random_device / srand / rand() / arc4random /
     /dev/urandom FAIL in scope (determinism law: no wall-clock, no
     unseeded randomness in decisions; hosts needing entropy take it as an
     injected argument — see update/core/backoff.cc's caller-supplied
     monotonic ints);
  5. std::hash FAILS unless dispositioned in STD_HASH_DISPOSITIONS below —
     "used for anything integrity-related" cannot be decided statically, so
     EVERY use is dispositioned in writing or refused;
  6. Rust (shield/**/*.rs): sha2/md5/blake2/ring/rustcrypto/rand crate uses
     FAIL outside the engine shim's recorded allowlist (none today).

ALLOWLIST  common/core/sha256.{h,cc} is the ONE sanctioned implementation
(S0-owned, KAT-pinned by common/tests/test_sha256_kat.cc in every consumer
lane). Alias shims (<core>/core/sha256.h re-exporting xr::common) are
sanctioned consumption, not copies: they carry no constants and no bodies.
`release/` tooling may use Python hashlib (out of scope by rule text above).

--self-test plants each rule's violation in a throwaway tree and proves the
scan reddens (a planted-copy fixture; the shell canary lives in
tools/negatives/p11_t0.sh). Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

SINGLE_COPY = {  # rule 0: filename -> the only sanctioned home
    "sha256.cc": "common/core/sha256.cc",
    "json.cc": "common/core/json.cc",
    "json_parse.cc": "common/core/json_parse.cc",
}
IMPL_ALLOWLIST = {  # rule 1: files allowed to carry algorithm constants
    "common/core/sha256.cc",
}
STD_HASH_DISPOSITIONS = {  # rule 5: file -> recorded reason (reviewed lines)
    "policy/core/cache.h":
        "std::hash<std::string> keys the in-memory LRU cache map — NOT "
        "integrity: no digest is compared, stored, persisted or transmitted "
        "(P6 cache design; a collision only co-locates two cache buckets). "
        "Recorded P11-T0-b; a second std::hash needs its own disposition.",
}

CONST_RE = re.compile(
    r"0x(6a09e667|bb67ae85|3c6ef372|a54ff53a|510e527f|9b05688c|1f83d9ab|"
    r"5be0cd19|428a2f98|71374491|b5c0fbcf|e9b5dba5|67452301|efcdab89|"
    r"98badcfe|10325476|d76aa478|5a827999|6ed9eba1|8f1bbcdc|ca273ece|"
    r"d186b8c7|a953fd4e|53657966|6ca62c2d|22ae2f1f)(?![0-9a-fA-F])", re.IGNORECASE)
LIB_INCLUDE_RE = re.compile(
    r'#\s*include\s*[<"](openssl/|boringssl|sodium\.h|libsodium|mbedtls/|'
    r'botan/|cryptopp/|crypto/|commoncrypto/)')
BANNED_SYMBOL_RE = re.compile(
    r"\b(Sha1|Sha512|Sha3|Sha384|Md4|Md5|Blake2[bs]?|Blake3|Keccak|Hmac[A-Z_]"
    r"|Pbkdf2|Hkdf|Scrypt|Argon2|Poly1305|ChaCha20|AesEncrypt|AesDecrypt"
    r"|Ed25519Sign|Ed25519Verify|X25519|crypto_sign|ge_p3|sc_reduce"
    r"|RsaSign|RsaVerify)\w*\b")
PRNG_RE = re.compile(
    r"\b(std::mt19937|std::random_device|mt19937|random_device|srand\s*\("
    r"|(?<![A-Za-z_])rand\s*\(\)|arc4random|/dev/urandom|/dev/random)")
RUST_CRYPTO_RE = re.compile(
    r"\b(use\s+(sha2|sha1|md5|md-5|blake2|blake3|ring|hmac|pbkdf2|hkdf"
    r"|ed25519_dalek|curve25519_dalek|rand)\b|extern\s+crate\s+"
    r"(sha2|ring|rand|rustcrypto)\b)")
STD_HASH_RE = re.compile(r"\bstd::hash\b")
STRIP_LITERALS_RE = re.compile(r'"(?:\\.|[^"\\])*"')
STRIP_LINE_COMMENT_RE = re.compile(r"//.*$")


def strip_noise(line: str) -> str:
    """Blank out string literals and line comments (prose/alg-ids are data)."""
    line = STRIP_LITERALS_RE.sub('""', line)
    return STRIP_LINE_COMMENT_RE.sub("", line)


def scan_file(path: Path, rel: str) -> list[str]:
    fails: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"{rel}: unreadable ({exc})"]
    is_impl = rel in IMPL_ALLOWLIST
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = strip_noise(raw)
        if not line.strip():
            continue
        if not is_impl and CONST_RE.search(line):
            fails.append(f"{rel}:{lineno}: algorithm constant outside the "
                         "single sanctioned implementation — a second copy "
                         "of a public algorithm is a defect (ADR-0043)")
        if LIB_INCLUDE_RE.search(line):
            fails.append(f"{rel}:{lineno}: crypto library include — no core "
                         "or shield file links a crypto library (DR-11)")
        if BANNED_SYMBOL_RE.search(line):
            fails.append(f"{rel}:{lineno}: banned primitive symbol — no "
                         "second algorithm (blake2/sha512/hmac/kdf/…) may "
                         "appear in scope; a real need is a stop-and-report "
                         "(P11 failure condition 4), not an edit")
        if PRNG_RE.search(line):
            fails.append(f"{rel}:{lineno}: PRNG/entropy source in scope — "
                         "decisions are deterministic (no unseeded "
                         "randomness; entropy is injected by the caller)")
        if STD_HASH_RE.search(line) and rel not in STD_HASH_DISPOSITIONS:
            fails.append(f"{rel}:{lineno}: std::hash without a recorded "
                         "disposition — integrity-adjacent hashing must use "
                         "the common/core single copy (ADR-0043)")
        if path.suffix == ".rs" and RUST_CRYPTO_RE.search(line):
            fails.append(f"{rel}:{lineno}: Rust crypto/rand crate use — the "
                         "engine shim binds adblock-rust only; crypto crates "
                         "are a dependency event (docs/dependencies/ row)")
    return fails


def scoped_files(xr_core: Path) -> list[Path]:
    out: list[Path] = []
    for core_dir in sorted(xr_core.glob("*/core")):
        if core_dir.is_dir():
            out.extend(sorted(core_dir.rglob("*.cc")) +
                       sorted(core_dir.rglob("*.h")))
    shield = xr_core / "shield"
    if shield.is_dir():
        for suffix in ("*.cc", "*.h", "*.rs"):
            out.extend(sorted(shield.rglob(suffix)))
    dedup: dict[Path, None] = {}
    for p in out:
        if "build" not in p.parts and "third_party" not in p.parts:
            dedup[p.resolve()] = None
    return [Path(p) for p in dedup]


def check_single_copy(xr_core: Path) -> list[str]:
    """Rule 0: the `find xr-core -name sha256.cc` proof, machine-run."""
    fails: list[str] = []
    for name, home in sorted(SINGLE_COPY.items()):
        found = sorted(p for p in xr_core.rglob(name)
                       if "build" not in p.parts and ".git" not in p.parts
                       and "third_party" not in p.parts)
        rels = [str(p.relative_to(xr_core)) for p in found]
        if rels != [home]:
            fails.append(f"single-copy law: {name} must exist exactly once, "
                         f"at {home} — found {rels or 'NONE'}")
    return fails


def run_check(xr_core: Path) -> list[str]:
    fails = check_single_copy(xr_core)
    for path in scoped_files(xr_core):
        fails.extend(scan_file(path, str(path.relative_to(xr_core))))
    return fails


SELF_TEST_FILES = {
    "evil/core/copy.cc":
        '#include "evil/core/copy.h"\n'
        'static const uint32_t H0 = 0x6a09e667u;  // planted SHA-256 copy\n'
        'std::string Sha256Hex(std::string_view d) { (void)d; return ""; }\n',
    "evil/core/lib.cc": '#include <openssl/sha.h>\nint f(){return 0;}\n',
    "evil/core/second_alg.h": 'void Blake2b(const char* p);\n',
    "evil/core/prng.cc":
        '#include <random>\nint f(){ std::mt19937 g; srand(1); return g(); }\n',
    "evil/core/hashmap.cc":
        '#include <functional>\nsize_t f(const std::string& s){'
        ' return std::hash<std::string>{}(s); }\n',
    "shield/engine/evil.rs": 'use sha2::Sha256;\nfn f() {}\n',
}


def self_test(xr_core: Path) -> int:
    """Plant each rule's violation in a throwaway tree; all must redden."""
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "xr-core"
        # the sanctioned single copy, so rule 0 does not mask the other rules
        for name, home in SINGLE_COPY.items():
            (fake / home).parent.mkdir(parents=True, exist_ok=True)
            (fake / home).write_text("// sanctioned\n", encoding="utf-8")
        (fake / "common/core/sha256.h").write_text("// sanctioned\n")
        for rel, body in SELF_TEST_FILES.items():
            p = fake / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        failures: list[str] = []
        for rel in SELF_TEST_FILES:
            fails = run_check(fake)
            if not any(rel in f for f in fails):
                failures.append(f"self-test: planted violation {rel} did NOT "
                                "redden the scan")
        # rule 0: a planted sixth copy of sha256.cc must redden on its own
        plant = fake / "shield" / "core" / "sha256.cc"
        plant.parent.mkdir(parents=True, exist_ok=True)
        plant.write_text("// planted copy\n", encoding="utf-8")
        if not any("single-copy law" in f for f in run_check(fake)):
            failures.append("self-test: planted second sha256.cc did NOT "
                            "redden rule 0")
        if failures:
            for f in failures:
                print(f"FAIL: {f}")
            print(f"FAIL: no_new_crypto_check --self-test ({len(failures)})")
            return EXIT_FAIL
        print("PASS: no_new_crypto_check --self-test (6 planted rule "
              "violations + 1 planted copy all reddened)")
        return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_core = Path(__file__).resolve().parent.parent.parent / "xr-core"
    ap.add_argument("--xr-core", default=str(default_core))
    ap.add_argument("--self-test", action="store_true",
                    help="prove the failure path works (planted violations)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    xr_core = Path(args.xr_core).resolve()
    if not xr_core.is_dir():
        print(f"error: no xr-core checkout at {xr_core}", file=sys.stderr)
        return EXIT_USAGE
    if args.self_test:
        return self_test(xr_core)

    files = scoped_files(xr_core)
    if not files:
        print("FAIL: scanned ZERO files — a scanner with no input certifies "
              "nothing (zero-case law)", file=sys.stderr)
        return EXIT_FAIL
    fails = run_check(xr_core)
    if args.json:
        print(json.dumps({"scanned": len(files), "failures": fails,
                          "status": "pass" if not fails else "fail"}, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        if not fails:
            print(f"PASS: no_new_crypto_check ({len(files)} file(s) scanned; "
                  "one sha256.cc, one json.cc, one json_parse.cc — all in "
                  "common/core; no constants/libs/banned symbols/PRNG/"
                  "undispositioned std::hash outside the allowlist)")
        else:
            print(f"FAIL: no_new_crypto_check ({len(fails)} finding(s))")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
