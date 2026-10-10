#!/usr/bin/env python3
"""tools/ledger_identity_check.py — the ledger-identity-overlay-v1 byte-law.

P14-T5 (P14-CLOSE C-2). Plan §4 P14 T5: "history/bookmarks identity tagging
via ledger overlay (upstream history untouched; omnibox results
filterable)"; contracts-out: "ledger identity_id everywhere".

What it proves, every governance run:
  1. every vector in docs/contracts/vectors/ledger-identity-overlay-v1.json
     replays BYTE-IDENTICALLY (stdout bytes + exit code) against BOTH
     backends: the compiled identity_host's living subcommands
     (xr-core/identity/host/identity_host.cc -> core/ledger_tag.cc) and the
     Python twin (xr-core/fakes/ledger_identity.py), and both equal the
     vector's expected bytes;
  2. coverage: every event class in the closed set has a tagging vector AND
     a missing-identity refusal vector (so "identity_id required" holds per
     class, not on average);
  3. every successful overlay record validates against
     docs/contracts/ledger-identity-overlay-v1.schema.json (tools/xr_schema),
     which REQUIRES identity_id;
  4. the zero-delta oracle: every history-oracle vector says "diff-clean",
     and the line `history-oracle: upstream history diff-clean (N vectors)`
     is printed (the plan's "upstream history untouched", made checkable);
  5. drift: the frozen ActivityKind enum, read LIVE from
     xr-core/mojom/activity_log.mojom, is a subset of the overlay classes.

--twin PATH: replay against an alternative Python twin ONLY (the negatives
pass a scratch copy with a planted defect: the omnibox leak, the upstream
write). The C++ half is not run, so a clean --twin run exits 77, never 0 —
it can never stand in for the gate's green.
--regen: rewrites the vectors file from the Python twin (deliberate; the
gate never passes it and never rewrites in-tree).

Exit: 0 pass · 1 fail · 2 usage/layout · 77 skip-visible (no g++/make: the
Python half still runs and the verdict says the C++ half was skipped).
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xr_sibling import resolve_or_exit  # noqa: E402
import xr_schema  # noqa: E402

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77
REPO = Path(__file__).resolve().parents[1]
VECTORS = REPO / "docs" / "contracts" / "vectors" / "ledger-identity-overlay-v1.json"
SCHEMA = REPO / "docs" / "contracts" / "ledger-identity-overlay-v1.schema.json"
CMDS = ("ledger-tag", "omnibox-filter", "history-oracle")
A = "xr:00000000-0000-4000-8000-00000000000a"
B = "xr:00000000-0000-4000-8000-00000000000b"


def _classes(twin_path: Path) -> tuple[str, ...]:
    ns: dict = {}
    exec(compile(twin_path.read_text(encoding="utf-8"), str(twin_path), "exec"), ns)
    return tuple(ns["CLASSES"])


def _inputs(classes: tuple[str, ...]) -> list[dict]:
    """The vector INPUTS (expected bytes come from --regen). Deterministic."""
    v: list[dict] = []
    for cls in classes:
        v.append({"id": f"tag-{cls}", "cmd": "ledger-tag",
                  "args": {"identity_id": A, "event_class": cls,
                           "event": {"kind": cls, "summary": "row"}}})
        v.append({"id": f"tag-{cls}-no-identity", "cmd": "ledger-tag",
                  "args": {"event_class": cls, "event": {"kind": cls}}})
    v += [
        {"id": "tag-empty-identity", "cmd": "ledger-tag",
         "args": {"identity_id": "", "event_class": "kBlock", "event": {}}},
        {"id": "tag-display-name-is-not-an-id", "cmd": "ledger-tag",
         "args": {"identity_id": "Work", "event_class": "kBlock", "event": {}}},
        {"id": "tag-unknown-class", "cmd": "ledger-tag",
         "args": {"identity_id": A, "event_class": "kTelemetry", "event": {}}},
        {"id": "tag-event-not-object", "cmd": "ledger-tag",
         "args": {"identity_id": A, "event_class": "kBlock", "event": [1]}},
        {"id": "args-not-object", "cmd": "ledger-tag", "args": [A]},
        {"id": "tag-unicode-event-bytes", "cmd": "ledger-tag",
         "args": {"identity_id": A, "event_class": "kHistory",
                  "event": {"title": "caf\u00e9 \u2014 \U0001f600"}}},
    ]
    mixed = [{"identity_id": A, "url": "https://a.example/"},
             {"identity_id": B, "url": "https://b-secret.example/"},
             {"url": "https://untagged.example/"},
             {"identity_id": "garbage", "url": "https://bad.example/"}]
    v += [
        {"id": "omnibox-a-sees-only-a", "cmd": "omnibox-filter",
         "args": {"identity_id": A, "rows": mixed}},
        {"id": "omnibox-b-sees-only-b", "cmd": "omnibox-filter",
         "args": {"identity_id": B, "rows": mixed}},
        {"id": "omnibox-no-identity-sees-nothing", "cmd": "omnibox-filter",
         "args": {"rows": mixed}},
        {"id": "omnibox-empty", "cmd": "omnibox-filter",
         "args": {"identity_id": A, "rows": []}},
        {"id": "omnibox-rows-not-array", "cmd": "omnibox-filter",
         "args": {"identity_id": A, "rows": {}}},
    ]
    hist = [{"url_id": 1, "visit_id": 10, "url": "https://a.example/",
             "title": "A", "ts": 1},
            {"url_id": 2, "visit_id": 11, "url": "https://b.example/",
             "title": "caf\u00e9", "ts": 2}]
    v += [
        {"id": "history-single-identity-zero-delta", "cmd": "history-oracle",
         "args": {"identity_id": A, "upstream_rows": hist}},
        {"id": "history-empty-zero-delta", "cmd": "history-oracle",
         "args": {"identity_id": A, "upstream_rows": []}},
        {"id": "history-unknown-upstream-field", "cmd": "history-oracle",
         "args": {"identity_id": A,
                  "upstream_rows": [{"url_id": 1, "identity_id": A}]}},
        {"id": "history-no-identity", "cmd": "history-oracle",
         "args": {"upstream_rows": hist}},
    ]
    return v


def _arg_text(args: dict) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"))


def _run(argv: list[str]) -> tuple[str, int]:
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    return r.stdout, r.returncode


def _build_host(xr_core: Path, build_dir: Path) -> Path | None:
    if not (shutil.which("g++") and shutil.which("make")):
        return None
    r = subprocess.run(["make", "-C", str(xr_core / "identity" / "tests"),
                        f"BUILD={build_dir}", str(build_dir / "identity_host")],
                       capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise SystemExit(f"ledger_identity_check: FAIL — make identity_host:\n"
                         f"{r.stderr[-600:]}")
    return build_dir / "identity_host"


def replay(vectors: list[dict], twin: Path, host: Path | None) -> list[str]:
    fails: list[str] = []
    for vec in vectors:
        text = _arg_text(vec["args"])
        want = (vec["expect_stdout"], vec["expect_exit"])
        got_py = _run([sys.executable, str(twin), vec["cmd"], text])
        if got_py != want:
            fails.append(f"{vec['id']}: python twin {got_py!r} != expected {want!r}")
        if host is not None:
            got_cc = _run([str(host), vec["cmd"], text])
            if got_cc != want:
                fails.append(f"{vec['id']}: identity_host {got_cc!r} != expected {want!r}")
            if got_cc != got_py:
                fails.append(f"{vec['id']}: backends differ (C++ vs Python)")
    return fails


def frozen_kinds(xr_core: Path) -> list[str]:
    """The frozen ActivityKind enum, read live from the mojom (never copied)."""
    text = (xr_core / "mojom" / "activity_log.mojom").read_text(encoding="utf-8")
    m = re.search(r"enum ActivityKind \{(.*?)\};", text, re.S)
    return re.findall(r"\b(k[A-Z]\w*)\s*=", m.group(1)) if m else []


def laws(vectors: list[dict], classes: tuple[str, ...],
         kinds: list[str]) -> tuple[list[str], int]:
    fails: list[str] = []
    have = [{k: v.get(k) for k in ("id", "cmd", "args")} for v in vectors]
    if have != _inputs(classes):
        fails.append("generator: vector inputs differ from _inputs() — the file "
                     "is generated (--regen), never hand-edited")
    if not kinds:
        fails.append("mojom: cannot read enum ActivityKind from activity_log.mojom")
    for k in kinds:
        if k not in classes:
            fails.append(f"drift: frozen ActivityKind {k} is not an overlay class")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    ids = {v["id"] for v in vectors}
    for cls in classes:
        for need in (f"tag-{cls}", f"tag-{cls}-no-identity"):
            if need not in ids:
                fails.append(f"coverage: no vector {need!r} (every class needs both)")
    oracle = 0
    for v in vectors:
        if v["cmd"] not in CMDS:
            fails.append(f"{v['id']}: unknown cmd {v['cmd']!r}")
            continue
        out = json.loads(v["expect_stdout"])
        if v["id"].endswith("-no-identity") and out.get("reason") != "identity-id-required":
            fails.append(f"{v['id']}: a missing identity_id must be refused")
        if v["cmd"] == "ledger-tag" and "error" not in out:
            errs = xr_schema.validate_document(out, schema)
            if errs:
                fails.append(f"{v['id']}: schema: {errs}")
        if v["cmd"] == "omnibox-filter" and "current" in out:
            for row in out["current"]:
                if row.get("identity_id") != out["identity_id"]:
                    fails.append(f"{v['id']}: cross-identity row in 'current'")
            for row in out["unknown"]:
                if row.get("provenance") != "unknown" or "identity_id" in row:
                    fails.append(f"{v['id']}: an unknown row is not typed unknown")
        if v["cmd"] == "history-oracle" and "verdict" in out:
            oracle += 1
            if out["verdict"] != "diff-clean":
                fails.append(f"{v['id']}: upstream history DELTA")
    return fails, oracle


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--regen", action="store_true")
    ap.add_argument("--twin", default=None)
    args = ap.parse_args(argv)
    xr_core = resolve_or_exit(REPO, override=args.xr_core,
                              tool="ledger_identity_check").path
    twin = xr_core / "fakes" / "ledger_identity.py"
    classes = _classes(twin)
    if args.regen:
        out = []
        for vec in _inputs(classes):
            so, rc = _run([sys.executable, str(twin), vec["cmd"], _arg_text(vec["args"])])
            out.append({**vec, "expect_stdout": so, "expect_exit": rc})
        doc = {"contract": "ledger-identity-overlay-v1", "schema_version": 1,
               "generator": "tools/ledger_identity_check.py --regen (Python twin); "
                            "replayed against BOTH backends by the gate",
               "vectors": out}
        VECTORS.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n",
                           encoding="utf-8")
        print(f"ledger_identity_check: wrote {len(out)} vectors to {VECTORS.name}")
        return EXIT_PASS
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]
    with tempfile.TemporaryDirectory(prefix="xr-ledger-id.") as td:
        if args.twin:
            twin, host = Path(args.twin).resolve(), None
        else:
            host = _build_host(xr_core, Path(td) / "build")
        fails = replay(vectors, twin, host)
    law_fails, oracle = laws(vectors, classes, frozen_kinds(xr_core))
    fails += law_fails
    for f in fails:
        print(f"FAIL: {f}")
    if not fails:
        print(f"history-oracle: upstream history diff-clean ({oracle} vectors)")
    halves = ("C++ identity_host + Python twin" if host else
              f"Python twin only ({'--twin ' + args.twin if args.twin else 'g++/make absent'}"
              f": C++ half SKIPPED)")
    verdict = "PASS" if not fails else "FAIL"
    print(f"{verdict}: ledger_identity_check ({len(vectors)} vectors, "
          f"{len(classes)} event classes, backends: {halves})")
    if fails:
        return EXIT_FAIL
    return EXIT_PASS if host else EXIT_SKIP


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
