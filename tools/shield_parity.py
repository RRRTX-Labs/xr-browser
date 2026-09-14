#!/usr/bin/env python3
"""T8 shield parity: the committed corpus vs BOTH engines (P11 brief T8).

Replays xr-core/shield/tests/corpus/parity-corpus-v1.json (>=1,500 cases,
machine-derived, expected verdicts committed) through:

  lane fake (local, default): xr-core fakes/shield.py decide_match — the
    Python mirror of the C++ TableEngine (byte-equivalence itself pinned
    by differential_smoke + the 465-vector golden replay through BOTH
    backends). Compares action, why_code, engine_decision, rule_id.
  lane real (hosted, --engine real --shim libxr_shield_engine.so): the
    vendored adblock-rust shim through ctypes — the SAME C ABI the C++
    core injects. Compares action (+ rule recovery through list/rule
    indices); provenance on "provenance-divergence-D5" tagged cases is
    reported, not enforced (documented in docs/shield/parity-divergences.md).

Bands (plan L312/L731/L739 + brief T8): action agreement >= 98% (±2%),
false-positive rate <= 0.5% of expected-allow cases (FP = expected allow,
engine said block/redirect/replace), provenance agreement >= 98%.

CLI: shield_parity.py [--core DIR] [--corpus PATH] [--engine fake|real]
        [--shim PATH] [--json] [--check]
exit 0 pass · 1 band failure/error · 2 usage · 77 SKIP (real lane with no
shim available locally — visible, never silent).
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import sys
from pathlib import Path

BAND_AGREE = 98.0
BAND_FP = 0.5
BAND_PROV = 98.0
BLOCKISH = {"block", "redirect", "replace"}
ACTION_FROM_HIT = {0: "block", 1: "allow", 2: "redirect", 3: "replace"}


def die(msg: str, code: int = 2) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


def load_fake(core: Path):
    path = core / "fakes" / "shield.py"
    if not path.is_file():
        raise SystemExit(f"error: no fake shield at {path}")
    sys.path.insert(0, str(core / "fakes"))
    spec = importlib.util.spec_from_file_location("xr_fake_shield", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Hit(ctypes.Structure):
    _fields_ = [("action", ctypes.c_uint8),
                ("list_index", ctypes.c_uint32),
                ("rule_index", ctypes.c_uint32),
                ("redirect_resource", ctypes.c_char_p)]


class RealLane:
    """ctypes binding to the shim's C ABI (xr_shield_engine.h)."""

    def __init__(self, shim: Path):
        self.lib = ctypes.CDLL(str(shim))
        self.lib.xr_shield_engine_create.restype = ctypes.c_void_p
        self.lib.xr_shield_engine_create.argtypes = [ctypes.c_char_p,
                                                     ctypes.POINTER(ctypes.c_char_p)]
        self.lib.xr_shield_engine_match.restype = ctypes.c_int
        self.lib.xr_shield_engine_match.argtypes = [ctypes.c_void_p] + \
            [ctypes.c_char_p] * 4 + [ctypes.POINTER(Hit)]
        self.lib.xr_shield_engine_alive.restype = ctypes.c_int
        self.lib.xr_shield_engine_alive.argtypes = [ctypes.c_void_p]
        self.lib.xr_shield_engine_free.argtypes = [ctypes.c_void_p]
        self.handles: dict[str, int] = {}
        self.lib_ref: dict[str, dict] = {}

    def bundle_handle(self, bid: str, doc: dict) -> int:
        if bid not in self.handles:
            raw = json.dumps(doc, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
            detail = ctypes.c_char_p()
            h = self.lib.xr_shield_engine_create(raw, ctypes.byref(detail))
            if not h:
                raise SystemExit(f"error: shim create failed for {bid}: "
                                 f"{detail.value!r}")
            if not self.lib.xr_shield_engine_alive(ctypes.c_void_p(h)):
                raise SystemExit(f"error: shim engine not alive for {bid}")
            self.handles[bid] = h
            self.lib_ref[bid] = doc
        return self.handles[bid]

    def decide(self, bid: str, doc: dict, parts: dict, rd: str) -> dict:
        h = self.bundle_handle(bid, doc)
        surface = f"{parts['scheme']}://{parts['host']}{parts['path']}"
        hit = Hit()
        rc = self.lib.xr_shield_engine_match(
            ctypes.c_void_p(h), surface.encode(), parts["host"].encode(),
            parts["path"].encode(), rd.encode(), ctypes.byref(hit))
        if rc != 1:
            return {"action": "allow", "engine_hit": False,
                    "why_code": "no-match", "rule_id": ""}
        action = ACTION_FROM_HIT.get(hit.action, "block")
        rule_id = ""
        doc = self.lib_ref[bid]
        lists = doc.get("lists", [])
        if hit.list_index < len(lists):
            rules = lists[hit.list_index].get("rules", [])
            if hit.rule_index < len(rules):
                rule_id = rules[hit.rule_index]["id"]
        why = {"block": "rule-blocked", "allow": "rule-allowed",
               "redirect": "rule-redirected",
               "replace": "rule-replaced"}[action]
        return {"action": action, "engine_hit": True, "why_code": why,
                "rule_id": rule_id}

    def close(self) -> None:
        for h in self.handles.values():
            self.lib.xr_shield_engine_free(ctypes.c_void_p(h))
        self.handles.clear()


class FakeLane:
    def __init__(self, core: Path):
        self.mod = load_fake(core)
        self.pin = self.mod.parse_posture_args({})
        self.bundles: dict[str, dict] = {}

    def bundle(self, bid: str, doc: dict) -> dict:
        if bid not in self.bundles:
            self.bundles[bid] = self.mod.parse_bundle(json.loads(
                json.dumps(doc, sort_keys=True)))
        return self.bundles[bid]

    def decide(self, bid: str, doc: dict, case: dict) -> dict:
        b = self.bundle(bid, doc)
        scheme = case["url"].split("://", 1)[0].lower()
        ctx = self.mod.parse_context({
            "identity": {"value": "xr:parity"},
            "origin": {"scheme": scheme,
                       "registrable_domain": case["rd"]},
            "url": case["url"], "request_class": case["request_class"]})
        out = self.mod.decide_match(ctx, b, [], 1000, self.pin)
        v = out["verdict"]
        return {"action": v["action"], "engine_hit": v["engine_decision"],
                "why_code": v["why_code"], "rule_id": v["rule_id"]}


def run(corpus: dict, lane, engine: str) -> dict:
    per_class: dict[str, dict] = {}
    mismatches: list[dict] = []
    totals = {"n": 0, "agree": 0, "prov": 0, "fp": 0, "fp_denom": 0,
              "fn": 0}
    for case in corpus["cases"]:
        bid = case["bundle"]
        doc = corpus["bundles"][bid]
        exp = case["expect"]
        if engine == "real":
            got = lane.decide(bid, doc, split_parts(case["url"]),
                              case["rd"])
        else:
            got = lane.decide(bid, doc, case)
        cls = per_class.setdefault(case["rule_class"], {
            "n": 0, "agree": 0, "prov": 0, "fp": 0, "fp_denom": 0})
        cls["n"] += 1
        totals["n"] += 1
        ok = got["action"] == exp["action"]
        # expected-allow cases are the FP denominator (the request should
        # have loaded); a blockish verdict there is a false positive.
        if exp["action"] == "allow":
            cls["fp_denom"] += 1
            totals["fp_denom"] += 1
            if got["action"] in BLOCKISH:
                cls["fp"] += 1
                totals["fp"] += 1
        elif exp["action"] in BLOCKISH and got["action"] == "allow":
            totals["fn"] += 1
        prov_ok = (got["engine_hit"] == exp["engine_hit"]
                   and got["why_code"] == exp["why_code"]
                   and got["rule_id"] == exp["rule_id"])
        if engine == "real" and "provenance-divergence-D5" in case["tags"]:
            prov_ok = True  # documented: the real engine reports no-hit
        if ok:
            cls["agree"] += 1
            totals["agree"] += 1
        if prov_ok:
            cls["prov"] += 1
            totals["prov"] += 1
        if not ok or not prov_ok:
            # 200, not 20: the 105-divergence round (D-7/D-8/D-9) proved
            # a 20-row cap cannot triage a whole-class divergence from a
            # hosted log; the --json dump is the triage artifact.
            if len(mismatches) < 200:
                mismatches.append({"id": case["id"],
                                   "class": case["rule_class"],
                                   "variant": case["variant"],
                                   "url": case["url"], "expect": exp,
                                   "got": got, "action_ok": ok,
                                   "provenance_ok": prov_ok})
    n = max(totals["n"], 1)
    fpd = max(totals["fp_denom"], 1)
    agree = 100.0 * totals["agree"] / n
    fp = 100.0 * totals["fp"] / fpd
    prov = 100.0 * totals["prov"] / n
    passed = (agree >= BAND_AGREE and fp <= BAND_FP and prov >= BAND_PROV)
    return {"tool": "shield_parity", "engine": engine, "cases": totals["n"],
            "action_agreement_pct": round(agree, 3),
            "false_positive_pct": round(fp, 3),
            "provenance_agreement_pct": round(prov, 3),
            "false_negatives": totals["fn"],
            "bands": {"agreement_min_pct": BAND_AGREE,
                      "fp_max_pct": BAND_FP,
                      "provenance_min_pct": BAND_PROV},
            "per_class": per_class, "mismatches": mismatches,
            "verdict": "PASS" if passed else "FAIL"}


def split_parts(url: str) -> dict:
    pos = url.find("://")
    scheme = url[:pos].lower()
    rest = url[pos + 3:]
    host_end = len(rest)
    for ch in "/?#":
        i = rest.find(ch)
        if i != -1:
            host_end = min(host_end, i)
    host = rest[:host_end].lower().split(":", 1)[0]
    pstart = rest.find("/")
    tail = rest[pstart:] if (pstart != -1 and pstart <= host_end) else "/"
    cut = len(tail)
    for ch in "?#":
        i = tail.find(ch)
        if i != -1:
            cut = min(cut, i)
    path = tail[:cut]
    return {"scheme": scheme, "host": host,
            "path": path if path.startswith("/") else "/" + path}


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--core", default=str(here.parent.parent / "xr-core"))
    ap.add_argument("--corpus", default="")
    ap.add_argument("--engine", default="fake", choices=["fake", "real"])
    ap.add_argument("--shim", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    core = Path(args.core)
    corpus_path = Path(args.corpus) if args.corpus else \
        core / "shield/tests/corpus/parity-corpus-v1.json"
    if not corpus_path.is_file():
        return die(f"no corpus at {corpus_path}")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    if corpus.get("schema") != "xr-shield-parity-corpus":
        return die("corpus schema mismatch")
    if corpus.get("case_count", 0) < 1500 or \
            len(corpus.get("cases", [])) < 1500:
        return die(f"corpus below the 1,500-case floor: "
                   f"{len(corpus.get('cases', []))}")
    if args.engine == "real":
        shim = Path(args.shim) if args.shim else \
            core / "shield/engine/target/release/libxr_shield_engine.so"
        if not shim.is_file():
            print(f"SKIP: real-engine lane needs the shim cdylib "
                  f"({shim}) — hosted lane only (no local cargo build)",
                  file=sys.stderr)
            return 77
        lane = RealLane(shim)
        try:
            rep = run(corpus, lane, "real")
        finally:
            lane.close()
    else:
        rep = run(corpus, FakeLane(core), "fake")
    if args.json:
        print(json.dumps(rep, sort_keys=True))
    else:
        print(f"shield_parity ({rep['engine']}): {rep['cases']} cases — "
              f"agreement {rep['action_agreement_pct']}% "
              f"(band >={BAND_AGREE}), FP {rep['false_positive_pct']}% "
              f"(band <={BAND_FP}), provenance "
              f"{rep['provenance_agreement_pct']}% (band >={BAND_PROV}), "
              f"FN {rep['false_negatives']} — {rep['verdict']}")
        for m in rep["mismatches"][:10]:
            print(f"  {m['id']} [{m['class']}/{m['variant']}] {m['url']} "
                  f"expect={m['expect']} got={m['got']}")
    if args.check and rep["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
