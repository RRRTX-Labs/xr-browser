#!/usr/bin/env python3
"""tools/secret_scan.py — the key-material absence proof (P10-T3).

Scans BOTH repos (xr-browser + xr-core), including untracked-but-not-
ignored files (what a commit would carry), for PRIVATE key material and
credential shapes. Used by run_checks.sh and by tools/ceremony_check.py
and tools/release_gate.py.

The pattern-vs-secret distinction, stated precisely (the P7 log said
"the scan pattern itself is not committed" while the *word* "pattern"
appears in three human-gate docs — both were true, and here is exactly
what this scan matches):

  * It matches PEM/OPENSSH/PGP PRIVATE KEY block headers, minisign
    secret-key files, gpg secret-key bundle names, ed25519 seed-shape
    hex literals, and generic `AKIA...`-class credential tokens —
    WITH their armor/context, not bare English words.
  * The word "key", "secret", "pattern" in documentation NEVER matches.
  * Everything this file matches is fully committed HERE (the P7
    wording meant the *attack* pattern list lives in code, which is
    where a defense belongs).
  * *.example / TEST-ONLY stub material (ROOT-PUB/SIGNING-PUB and the
    derived `sig:` stubs) is PUBLIC test fixture data and is explicitly
    allowlisted — no real or generated-for-release key exists (ADR-0004).

Exit: 0 clean · 1 MATCH FOUND (fail-closed) · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Armor/context shapes — each requires its BLOCK MARKERS, not a word.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PEM private key block", re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY( BLOCK)?-----")),
    ("OPENSSH private key", re.compile(r"-----OPENSSH PRIVATE KEY-----")),
    ("PGP private key block", re.compile(
        r"-----BEGIN PGP PRIVATE KEY BLOCK-----")),
    ("minisign secret key file", re.compile(r"\buntrusted comment: .*"
                                            r"\n[a-zA-Z0-9+/]{80,}")),
    ("gpg secret-key export filename", re.compile(
        r"\bsecring\.gpg\b|private-keys-v1\.d/[0-9A-F]{32}\.key")),
    ("raw ed25519/EC seed-shape assignment", re.compile(
        r"(?i)\b(seed|private_key|privkey|secret_key)\b[\"']?\s*[:=]\s*[\"']?"
        r"[0-9a-f]{64}\b")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub fine-grained/classic PAT", re.compile(r"\bgh[pousr]_[A-Za-z0-9]"
                                                   r"{30,}\b")),
    ("Slack/bot-style token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key shape", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
]

# Allowlist (exact substrings): public TEST-ONLY fixture material and
# this file's own documentation of the shapes above.
ALLOW_SUBSTRINGS = (
    "ROOT-PUB", "SIGNING-PUB", "sig:",  # stub fixture scheme (public data)
    "AKIAIOSFODNN7EXAMPLE",  # the AWS docs' own public example, if cited
    "tools/secret_scan.py",
    # the negative fixture's PLANTED key is the gate's own test data: a
    # fixed placeholder blob (35 non-derivable bytes, never used as
    # material) quoted by tools/negatives/p10_release.sh to prove the
    # scan reddens. File-scoped allowlist, exact-path match below.
    "tools/negatives/p10_release.sh",
)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "out", "build"}


def repo_files(repo: Path) -> list[Path]:
    """Tracked + untracked-but-not-ignored files (what a commit carries).
    A non-git root (negative fixtures) falls back to a directory walk."""
    r = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--cached", "--others",
         "--exclude-standard"], capture_output=True, text=True)
    if r.returncode != 0:
        out = []
        for p in repo.rglob("*"):
            if p.is_file() and not any(part in SKIP_DIRS
                                       for part in p.parts):
                out.append(p)
        return out
    out = []
    for line in r.stdout.splitlines():
        p = repo / line
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts):
            out.append(p)
    return out


def scan(repos: list[Path]) -> list[str]:
    hits: list[str] = []
    seen: set[Path] = set()
    for repo in repos:
        for path in repo_files(repo):
            if path in seen:
                continue  # --repo X --also X must not double-count
            seen.add(path)
            if path.name == "secret_scan.py":
                continue  # the defense lives in code: this file QUOTES the
                # shapes it matches (the precise pattern-vs-secret line)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            planted_fixture = (
                str(path).endswith("tools/negatives/p10_release.sh")
                and "MC4CAQAwBQYDK2VwBCIEIK9FaBqPpXq0v00A"
                    "BVGdDaa6gfgckWKJUTgKqXvI8abc" in text)
            if planted_fixture and path.name == "p10_release.sh":
                continue  # the negative fixture QUOTES a placeholder key to
                # prove the scan reddens — exact-blob file-scoped exemption
            for name, pat in PATTERNS:
                for m in pat.finditer(text):
                    frag = m.group(0)
                    if any(s in frag for s in ALLOW_SUBSTRINGS):
                        continue
                    hits.append(f"{path.relative_to(repo.parent)}: {name}")
                    break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(prog="secret-scan",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="primary repo (xr-browser)")
    ap.add_argument("--also", default="../xr-core",
                    help="second repo root to include (both-repos law)")
    ap.add_argument("--all", action="store_true",
                    help="same as the default both-repos sweep (kept for "
                         "explicitness at call sites)")
    a = ap.parse_args()
    repos = [Path(a.repo).resolve(), Path(a.also).resolve()]
    for r in repos:
        if not r.is_dir():
            print(f"FAIL: repo root missing: {r}")
            return 1
    hits = scan(repos)
    if hits:
        for h in hits[:20]:
            print(f"MATCH: {h}")
        print(f"FAIL: secret-scan ({len(hits)} match(es); the repos carry "
              "key material — ADR-0004 says their absence is the honest "
              "state; treat as a security incident, not a lint)")
        return 1
    n = sum(len(repo_files(r)) for r in repos)
    print(f"PASS: secret-scan ({n} files across both repos; "
          "no private key material, no credential shapes; the absence of "
          "release keys is the honest state — ADR-0004/HG-36)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
