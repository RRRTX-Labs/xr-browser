#!/usr/bin/env python3
"""tools/release_gate.py — `./scripts/build release check --channel <c>`
(P10-T9): the single command that must be GREEN before any artifact is
called a release. Fail-CLOSED: in this sandbox (no real signing provider)
beta/stable MUST exit non-zero with the missing items enumerated — that
behavior IS the deliverable ("gate certifies nothing without a signature
provider").

Consumes (each a lane with its own gate elsewhere — this tool is the
release-time conjunction):
  * signing        release channel => requires a real provider (XR_SIGN_
                   PROVIDER); dev/nightly-test => the TEST-ONLY banner
  * sbom           build/sbom/sbom_gate.py (+ --require-licenses) on the
                   emitted SBOM (synthetic fixture here when no build)
  * license-report build/sbom/license_report.py (unknown-license => FAIL)
  * attestation    tools/attest.py --verify clean for the artifact set
  * evidence       evidence_check --strict for the phase bundle
  * leak-report    the P9 §11.8 hook (leaktest artifact for this train)
  * notes/CVE      tools/release_notes.py --check + claims_lint
  * drills         rollout_drill (cells > 0) transcript present

Exit: 0 green · 1 RED (missing items enumerated) · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RELEASE_CHANNELS = ("beta", "stable")
SIGNABLE_CHANNELS = ("dev", "nightly-test")


def run(cmd: list[str], **kw) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       **kw)
    return r.returncode, (r.stdout + r.stderr).strip()


class Gate:
    def __init__(self, channel: str) -> None:
        self.channel = channel
        self.missing: list[str] = []
        self.green: list[str] = []

    def lane(self, name: str, ok: bool, detail: str) -> None:
        (self.green if ok else self.missing).append(
            f"{name}: {detail}" + ("" if ok else " — MISSING/BLOCKED"))
        print(f"  [{'ok' if ok else 'XX'}] {name}: {detail}")

    def summary(self) -> int:
        print(f"\nrelease gate — channel {self.channel!r}: "
              f"{len(self.green)} lane(s) green, {len(self.missing)} missing")
        if self.missing:
            for m in self.missing:
                print(f"  MISSING: {m}")
            print(f"FAIL: release check --channel {self.channel} — the "
                  "gate certifies nothing without its evidence; do not "
                  "call this a release")
            return 1
        print(f"PASS: release check --channel {self.channel}")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="release check",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="run the release gate")
    chk.add_argument("--channel", required=True,
                     help="dev | nightly-test | beta | stable")
    chk.add_argument("--artifact", default=None,
                     help="artifact file (synthetic OK for dev)")
    chk.add_argument("--sbom", default=None)
    chk.add_argument("--attestation", default=None)
    a = ap.parse_args()
    if a.cmd != "check":
        ap.print_usage()
        return 2
    channel = a.channel
    if channel not in SIGNABLE_CHANNELS + RELEASE_CHANNELS:
        print(f"FAIL: unknown channel {channel!r}")
        return 2
    g = Gate(channel)
    artifact = Path(a.artifact) if a.artifact else \
        REPO / "work" / "release-check" / "synthetic-artifact.bin"

    print(f"== release gate: channel {channel} ==")
    # 1. signing ----------------------------------------------------------
    provider = os.environ.get("XR_SIGN_PROVIDER", "")
    if channel in RELEASE_CHANNELS:
        if channel in ("beta", "stable"):
            g.lane("signing", False,
                   f"channel {channel} requires a real signing provider "
                   f"(XR_SIGN_PROVIDER) + HG-36/37 credentials; got "
                   f"{provider!r}")
        else:
            g.lane("signing", bool(provider), f"provider {provider!r}")
    else:
        print(f"  [--] signing: TEST-ONLY banner (dev lane — the core "
              "prints 'test-only: …' on every accept; HG-36 for production)")
        g.lane("signing", True, "dev/nightly-test: TEST-ONLY is the honest "
               "state, banner in every result")
    # 2. SBOM + license law ------------------------------------------------
    sbom = Path(a.sbom) if a.sbom else REPO / "work" / "release-check" / \
        "sbom.json"
    sbom.parent.mkdir(parents=True, exist_ok=True)
    r1, _ = run([sys.executable, "build/sbom/emit_sbom.py", "--fixture",
                 "--out", str(sbom)])
    if artifact.exists():
        r1 = 0
    r2, _ = run([sys.executable, "build/sbom/license_report.py",
                 "--attach-to", str(sbom), "--out", str(sbom)])
    r3, out3 = run([sys.executable, "build/sbom/sbom_gate.py", "--sbom",
                    str(sbom), "--require-licenses"])
    g.lane("sbom+licenses", r1 == 0 and r2 == 0 and r3 == 0,
           out3.splitlines()[-1] if out3 else "gate rc "
           f"{r1}/{r2}/{r3}")
    # 3. attestation -------------------------------------------------------
    att = Path(a.attestation) if a.attestation else \
        REPO / "release" / "transparency" / "attestation-example.json"
    if channel in RELEASE_CHANNELS:
        g.lane("attestation", False,
               "release attestation must be built for THIS artifact set "
               "and signed by the production key (HG-36); the committed "
               "example is TEST-ONLY")
    else:
        rc, out = run([sys.executable, "tools/attest.py", "--verify",
                       str(att)])
        g.lane("attestation", rc == 0,
               out.splitlines()[0] if out else f"verify rc {rc}")
    # 4. evidence bundle (strict) -----------------------------------------
    rc, out = run([sys.executable, "tools/evidence_check.py", "--strict"])
    g.lane("evidence", rc == 0,
           out.splitlines()[-1] if out else f"evidence_check rc {rc}")
    # 5. leak-report artifact (P9 §11.8 hook) ------------------------------
    leak = REPO / "evidence" / "P9" / "logs" / "leaktest.txt"
    if not leak.exists():
        for cand in sorted((REPO / "evidence").rglob("*leak*")):
            if cand.is_file():
                leak = cand
                break
    if channel in RELEASE_CHANNELS:
        g.lane("leak-report", False,
               "a leak-report artifact for THIS train is required (P9 "
               "harness on the release artifacts; §11.8)")
    else:
        g.lane("leak-report", leak.exists(),
               str(leak.relative_to(REPO)) if leak.exists() else
               "no leak artifact found")
    # 6. notes + voice ------------------------------------------------------
    rc1, _ = run([sys.executable, "tools/release_notes.py", "--train", "152",
                  "--out", "release/notes/train-152.md", "--check"])
    rc2, _ = run([sys.executable, "tools/claims_lint.py"])
    g.lane("notes+voice", rc1 == 0 and rc2 == 0,
           "release_notes --check + claims_lint" +
           ("" if rc1 == 0 and rc2 == 0 else " FAILED"))
    # 7. drills -------------------------------------------------------------
    drill = REPO / "evidence" / "P10" / "logs" / "t5-rollout-drill.txt"
    ok = drill.exists() and "cells executed: 10" in \
        drill.read_text(encoding="utf-8")
    g.lane("drills", ok, "rollout drill transcript (10/10 cells)" if ok
           else "rollout drill transcript missing or incomplete")
    # 8. the channel law itself ---------------------------------------------
    if channel in RELEASE_CHANNELS:
        g.lane("auto-rollout-refusal", True,
               "beta/stable auto-rollout remains refused until P38 "
               "(policy.yaml; promotion is a human act this phase)")

    return g.summary()


if __name__ == "__main__":
    sys.exit(main())
