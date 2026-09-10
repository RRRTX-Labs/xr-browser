#!/usr/bin/env python3
"""tools/visual_diff.py — the snapshot comparison CLI (P9-T6).

Compares a reference PNG against a candidate PNG with the stdlib codec +
engine (build/qa/visual/), a threshold for AA tolerance, per-region ignore
lists, and a waiver registry with expiries:

  * identical                     -> IDENTICAL (pass)
  * different + unexpired waiver  -> WAIVED   (pass, recorded)
  * different + EXPIRED waiver    -> FAIL (an expired waiver must re-assert)
  * different, no waiver          -> DIFFERENT (fail)

The engine is real here; the captures + Gold bridge are farm (docs/qa/
gold-triage.md) — never a fake Gold connection.

``--self-test`` proves the discrimination on synthetic images: identical
(clean), 1-pixel diff (flagged), theme-swapped (flagged), RTL-mirrored
(flagged), below/above threshold — plus the waiver-expiry law. A comparator
that cannot flag a must-flag pair exits non-zero.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build.qa import _common as c  # noqa: E402
EXIT_FAIL = c.EXIT_FAIL
EXIT_PASS = c.EXIT_PASS
EXIT_USAGE = c.EXIT_USAGE
from build.qa.visual import engine, pngcodec  # noqa: E402


def load_waivers(path: Path) -> list[dict[str, Any]]:
    import yaml
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise c.RunnerError(f"{path}: unsupported waivers schema_version")
    return list(doc.get("waivers") or [])


def find_waiver(waivers: list[dict[str, Any]], name: str,
                ref_hash: str) -> dict[str, Any] | None:
    for w in waivers:
        if w.get("snapshot") == name and w.get("reference_hash") == ref_hash:
            return w
    return None


def compare_files(ref: Path, cand: Path, *, threshold: int,
                  ignore: list[engine.Region], waivers: list[dict[str, Any]],
                  meta: dict[str, Any] | None) -> dict[str, Any]:
    ref_img = pngcodec.decode(ref.read_bytes())
    cand_img = pngcodec.decode(cand.read_bytes())
    ref_hash = engine.sha256_png(ref.read_bytes())
    record = engine.diff(ref_img, cand_img, threshold=threshold, ignore=ignore)
    name = (meta or {}).get("name", ref.stem)
    if record["identical"]:
        verdict = "IDENTICAL"
    else:
        w = find_waiver(waivers, name, ref_hash)
        if w is None:
            verdict = "DIFFERENT"
        else:
            try:
                when = date.fromisoformat(w["expiry"])
            except (KeyError, ValueError):
                verdict = "DIFFERENT"   # malformed waiver is no waiver
            else:
                verdict = "WAIVED" if when >= date.today() else "DIFFERENT"
                if verdict == "DIFFERENT":
                    record["expired_waiver"] = w.get("id")
    record["verdict"] = verdict
    record["reference_hash"] = ref_hash
    record["candidate_hash"] = engine.sha256_png(cand.read_bytes())
    return record


def _mk(w: int, h: int, color: tuple[int, int, int]) -> pngcodec.Image:
    rgba = bytearray()
    for _ in range(w * h):
        rgba += bytes(color) + b"\xff"
    return pngcodec.Image(w, h, rgba)


def self_test(tmp: Path) -> int:
    """Synthetic discrimination proof + the waiver-expiry law."""
    checks: dict[str, bool] = {}
    a = _mk(16, 16, (200, 30, 30))
    b = _mk(16, 16, (200, 30, 30))
    checks["identical_clean"] = engine.diff(a, b)["identical"]

    one_px = _mk(16, 16, (200, 30, 30))
    one_px.rgba[0] = 201
    checks["one_px_flagged"] = not engine.diff(a, one_px)["identical"]

    theme = _mk(16, 16, (30, 30, 200))
    checks["theme_swap_flagged"] = not engine.diff(a, theme)["identical"]

    # horizontal mirror of a left/right-distinct image (the RTL case): the
    # left half is red, the right half green, so the mirror always differs.
    lr = _mk(16, 16, (200, 30, 30))
    for y in range(16):
        for x in range(8, 16):
            i = (y * 16 + x) * 4
            lr.rgba[i:i + 4] = bytes((30, 200, 30, 255))
    rtl = pngcodec.Image(16, 16, bytearray(lr.rgba))
    for y in range(16):
        for x in range(16):
            i = (y * 16 + x) * 4
            rtl.rgba[i:i + 4] = lr.rgba[(y * 16 + (15 - x)) * 4:
                                       (y * 16 + (15 - x)) * 4 + 4]
    checks["rtl_mirror_flagged"] = not engine.diff(lr, rtl)["identical"]

    low = _mk(16, 16, (200, 30, 30))
    low.rgba[0] = 201          # 1-delta on the R channel only
    checks["below_threshold_ignored"] = \
        engine.diff(a, low, threshold=2)["identical"]

    # waiver-expiry law: a DIFFERING candidate with an expired waiver is RED.
    (tmp / "a.png").write_bytes(pngcodec.encode(a))
    (tmp / "b.png").write_bytes(pngcodec.encode(one_px))
    waivers = [{"snapshot": "panel",
                "reference_hash": engine.sha256_png(pngcodec.encode(a)),
                "reason": "test", "owner": "t", "expiry": "2000-01-01"}]
    rec = compare_files(tmp / "a.png", tmp / "b.png", threshold=0,
                        ignore=[], waivers=waivers, meta={"name": "panel"})
    checks["expired_waiver_red"] = rec["verdict"] == "DIFFERENT"

    # and a VALID waiver turns the same diff into a pass.
    waivers[0]["expiry"] = "2999-01-01"
    rec2 = compare_files(tmp / "a.png", tmp / "b.png", threshold=0,
                         ignore=[], waivers=waivers, meta={"name": "panel"})
    checks["valid_waiver_green"] = rec2["verdict"] == "WAIVED"

    bad = [k for k, v in checks.items() if not v]
    if bad:
        print(f"FAIL: visual_diff self-test — {bad}")
        return EXIT_FAIL
    print("PASS: visual_diff self-test (identical clean; 1px/theme/RTL "
          "flagged; threshold honored; expired waiver red; valid waiver green)")
    return EXIT_PASS

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="visual_diff", description=__doc__)
    p.add_argument("--ref", help="reference PNG")
    p.add_argument("--cand", help="candidate PNG")
    p.add_argument("--threshold", type=int, default=0,
                   help="per-channel AA tolerance (default 0)")
    p.add_argument("--ignore-regions", default="",
                   help="JSON file of {x,y,w,h} rects to exclude (AA-edges)")
    p.add_argument("--waivers", default="build/qa/visual/waivers.yaml")
    p.add_argument("--meta", default="", help="snapshot metadata JSON")
    p.add_argument("--report-json", default="")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--json", action="store_true")
    c.as_of_arg(p)
    args = p.parse_args(argv)

    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for name, img in (("a", _mk(16, 16, (200, 30, 30))),
                              ("b", _mk(16, 16, (200, 30, 30)))):
                (tdir / f"{name}.png").write_bytes(pngcodec.encode(img))
            return self_test(tdir)

    if not args.ref or not args.cand:
        print("FAIL: --ref and --cand are required (usage error)")
        return c.EXIT_USAGE
    repo = Path(".").resolve()
    ref = Path(args.ref)
    cand = Path(args.cand)
    if not ref.is_absolute():
        ref = repo / ref
    if not cand.is_absolute():
        cand = repo / cand

    ignore: list[engine.Region] = []
    if args.ignore_regions:
        ip = Path(args.ignore_regions)
        if not ip.is_absolute():
            ip = repo / ip
        for r in json.loads(ip.read_text(encoding="utf-8")):
            ignore.append(engine.Region(r["x"], r["y"], r["w"], r["h"]))
    waivers: list[dict[str, Any]] = []
    wp = Path(args.waivers)
    if not wp.is_absolute():
        wp = repo / wp
    if wp.exists():
        waivers = load_waivers(wp)
    meta: dict[str, Any] | None = None
    if args.meta:
        mp = Path(args.meta)
        if not mp.is_absolute():
            mp = repo / mp
        meta = json.loads(mp.read_text(encoding="utf-8"))

    record = compare_files(ref, cand, threshold=args.threshold,
                           ignore=ignore, waivers=waivers, meta=meta)
    record["as_of"] = c.iso(args.as_of)
    if args.report_json:
        rp = Path(args.report_json)
        if not rp.is_absolute():
            rp = repo / rp
        rp.write_text(c.stable_json(record) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(record, sort_keys=True, indent=2))
    else:
        print(f"visual_diff: {record['differing_pixels']} differing px, "
              f"max_delta {record['max_delta']}, "
              f"{record['ignored_pixels']} ignored")
        print(f"{record['verdict']}: visual_diff")
    ok = record["verdict"] in ("IDENTICAL", "WAIVED")
    return c.EXIT_PASS if ok else c.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
