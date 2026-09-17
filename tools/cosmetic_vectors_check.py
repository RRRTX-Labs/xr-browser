#!/usr/bin/env python3
"""tools/cosmetic_vectors_check.py — golden-vector BYTE-PARITY across both
cosmetic backends (P12-T1; the shield_vectors_check.py pattern applied to the
renderer/cosmetic surface).

For every case in docs/contracts/vectors/cosmetic-v1.json this tool runs:
  * the compiled C++ host (xr-core/cosmetic/tests/build/cosmetic_host, built
    via its Makefile when absent — SKIP-visible without g++/make), and
  * the Python reference fake (xr-core/fakes/cosmetic.py),
feeds the SAME canonical request frame (or `raw` frame verbatim) plus the
case's `flags` to both, and requires:
  * byte-identical stdout between the backends AND versus the vector's
    `expect` (canonical bytes),
  * identical exit codes, matching the pinned `exit` or the derivation
    rule (error kMalformedInput/kUnknownMethod => 1, else 0).

Exit: 0 pass · 1 drift · 2 usage · 77 skip (tool absent: g++/make).
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

VECTORS = "docs/contracts/vectors/cosmetic-v1.json"
DEFAULT_XR_CORE = "../xr-core"


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)



def _cpp_names(src: Path, enum: str) -> set[str]:
    """Refusal names from a C++ *ErrorName() switch, extracted not copied."""
    import re
    if not src.is_file():
        return set()
    text = src.read_text(encoding="utf-8")
    return set(re.findall(rf"case {enum}::\w+: return \"([a-z0-9-]+)\";", text))


def _vocabulary_diff(xr_core: Path) -> list[str]:
    """Compare the C++ refusal vocabularies against the Python fake's sets."""
    import re
    sys.path.insert(0, str(xr_core / "fakes"))
    try:
        import cosmetic as fake  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return [f"cannot import fakes/cosmetic.py: {exc}"]
    finally:
        sys.path.pop(0)
    core = xr_core / "renderer" / "cosmetic" / "core"
    fails: list[str] = []
    # selector.cc's table includes "ok", which is not a refusal.
    for src_name, enum, py_set in (
        ("selector.cc", "SelectorError", fake.PARSER_REASONS),
        ("keyset.cc", "KeySetError", None),
        ("style.cc", "StyleError", fake.STYLE_REASONS),
    ):
        cpp = _cpp_names(core / src_name, enum) - {"ok"}
        if py_set is None:
            continue
        if cpp != py_set:
            fails.append(
                f"{src_name} {enum} vocabulary diverges from "
                f"fakes/cosmetic.py — C++ only: {sorted(cpp - py_set)}, "
                f"fake only: {sorted(py_set - cpp)}")
    # The fake's refusal names must all be names some C++ table produces, so a
    # name invented on the Python side cannot pass quietly.
    all_cpp = set()
    for src_name, enum in (("selector.cc", "SelectorError"),
                           ("keyset.cc", "KeySetError"),
                           ("style.cc", "StyleError"),
                           ("blob.cc", "BlobError")):
        all_cpp |= _cpp_names(core / src_name, enum)
    invented = fake.REFUSAL_REASONS - all_cpp - {
        # Blob-level reasons the contract defines in prose rather than in an
        # *ErrorName() switch.
        "rule-too-large", "no-executable-content",
    }
    if invented:
        fails.append(f"fakes/cosmetic.py names refusals no C++ table produces: "
                     f"{sorted(invented)}")
    return fails


def frame_for(case: dict) -> str:
    if "raw" in case:
        return case["raw"]
    return canonical({"args": case["args"], "method": case["method"]})


def run(cmd: list[str], frame: str) -> tuple[str, int]:
    r = subprocess.run(cmd, input=frame, capture_output=True, text=True,
                       timeout=60)
    return r.stdout.strip("\n"), r.returncode


def want_rc(case: dict) -> int:
    if "exit" in case:
        return int(case["exit"])
    expect = case["expect"]
    if isinstance(expect, dict) and "error" in expect and "ok" not in expect:
        return 1 if expect["error"] in ("kMalformedInput",
                                        "kUnknownMethod") else 0
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="cosmetic-vectors-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xr_core = Path(a.xr_core).resolve() if a.xr_core else \
        (repo / DEFAULT_XR_CORE).resolve()

    vec_path = repo / VECTORS
    try:
        doc = json.loads(vec_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {vec_path}: {exc}")
        return 1
    cases = doc.get("cases") or []
    if not cases:
        print("FAIL: zero vector cases — a runner that runs nothing "
              "certifies nothing")
        return 1
    if len(cases) < 150:
        print(f"FAIL: {len(cases)} cases (<150 — the P11-T2 floor)")
        return 1

    host_bin = (xr_core / "renderer" / "cosmetic" / "tests" / "build" /
            "cosmetic_host")
    if not host_bin.exists():
        mk = subprocess.run(["make", "-C",
                             str(xr_core / "renderer" / "cosmetic" /
                                 "tests"), "build"],
                            capture_output=True, text=True)
        if mk.returncode != 0 or not host_bin.exists():
            print("SKIP: SKIP (tool absent: g++/make) — needed for: building "
                  "cosmetic_host for the C++ side of the byte-parity harness; "
                  "local hint: apt-get install g++ make (build-essential)")
            return 77
    fake = xr_core / "fakes" / "cosmetic.py"
    if not fake.exists():
        print(f"FAIL: fake not found at {fake}")
        return 2

    # MECHANICAL VOCABULARY DIFF (P12-T1). Two implementations of one refusal
    # vocabulary WILL drift, and both looking 24-ish entries long is not
    # evidence they agree: fakes/cosmetic.py shipped "comment-unterminated"
    # where selector.cc said "comment-refused", and nothing caught it until the
    # sets were diffed by machine. The names are extracted from the C++ source
    # rather than copied, so a rename on either side reddens this gate instead
    # of drifting into the vectors.
    vocab_fails = _vocabulary_diff(xr_core)
    for f in vocab_fails:
        print(f"FAIL: {f}")
    if vocab_fails:
        return 1

    drift = 0
    for case in cases:
        cid = case["id"]
        frame = frame_for(case)
        flags = shlex.split(case.get("flags", ""))
        want = canonical(case["expect"])
        rc_want = want_rc(case)
        h_out, h_rc = run([str(host_bin), *flags], frame)
        f_out, f_rc = run([sys.executable, str(fake), *flags], frame)
        if h_out != want or f_out != want or h_rc != rc_want or \
                f_rc != rc_want:
            drift += 1
            print(f"DRIFT {cid} (want rc={rc_want})\n"
                  f"  want: {want[:220]}\n"
                  f"  host(rc={h_rc}): {h_out[:220]}\n"
                  f"  fake(rc={f_rc}): {f_out[:220]}")
    if drift:
        print(f"FAIL: {drift}/{len(cases)} vector cases drifted")
        return 1
    print(f"PASS: {len(cases)} cosmetic vectors byte-identical across "
          "cosmetic_host (C++) and fakes/cosmetic.py (Python)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
