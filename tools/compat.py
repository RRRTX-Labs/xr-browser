#!/usr/bin/env python3
"""tools/compat.py — compat-corpus runner (P9-T4, §11.12).

Three modes, each honest about what runs where:

  validate  — schema-check the corpus (xr-core/test/corpus/corpus.yaml):
              every entry has id/class/url_class/flows/expectations/owner/
              provenance/mode, expectations use only known keys, and every
              `replay` fixture is present. Empty-run law: zero entries is a
              FAILURE.
  replay    — offline replay: load each fixture and assert it genuinely
              exercises its flow class (FLOW_MARKERS). Real here: a login
              fixture without a password field is a failure.
  live      — REFUSED unless XR_LIVE_NET=1 AND the target host is on the
              fetch.py allowlist (none is, for web hosts). The live-mode law
              (L10-ish): corpus contents are reviewed before any live fetch;
              this repo adds no hosts to the allowlist for it — if a real
              host were needed, that is a stop-and-report.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage · 77 skip (live mode without
permission).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build.qa import _common as c  # noqa: E402
from build.qa.compat import flow_classes as fc  # noqa: E402

CORPUS_YAML = "../xr-core/test/corpus/corpus.yaml"


def fixtures_dir(repo: Path) -> Path:
    """Replay fixtures live beside the corpus (in the product tree)."""
    p = repo / CORPUS_YAML
    return p.parent / "replay-fixtures"


def load_corpus(repo: Path) -> dict:
    import yaml
    p = repo / CORPUS_YAML
    if not p.exists():
        raise c.RunnerError(f"missing corpus at {p}")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise c.RunnerError(f"{p}: unsupported corpus schema_version")
    return doc


def validate(repo: Path, corpus: dict) -> list[str]:
    fails: list[str] = []
    fx = fixtures_dir(repo)
    entries = corpus.get("entries") or []
    if not entries:
        fails.append("corpus: zero entries (empty-run law)")
        return fails
    seen: set[str] = set()
    for e in entries:
        eid = e.get("id")
        if eid in seen:
            fails.append(f"{eid}: duplicate id")
        seen.add(eid)
        for field in ("id", "class", "url_class", "flows", "expectations",
                      "owner", "provenance", "mode"):
            if not e.get(field):
                fails.append(f"{eid or '?'}: missing/empty {field!r}")
        if e.get("class") not in {"top500", "regional", "hardapp"}:
            fails.append(f"{eid}: class {e.get('class')!r} not in "
                         f"{{top500, regional, hardapp}}")
        bad = set(e.get("expectations", {})) - fc.EXPECTATION_KEYS
        if bad:
            fails.append(f"{eid}: unknown expectation keys {sorted(bad)}")
        if e.get("mode") == "expectations-only" and e.get("replay"):
            if not (fx / e["replay"]).exists():
                fails.append(f"{eid}: replay fixture {e['replay']} missing")
    return fails


def replay(repo: Path, corpus: dict) -> list[str]:
    fails: list[str] = []
    fx = fixtures_dir(repo)
    n = 0
    for e in corpus.get("entries") or []:
        if e.get("mode") != "expectations-only" or not e.get("replay"):
            continue
        path = fx / e["replay"]
        text = path.read_text(encoding="utf-8", errors="replace")
        markers = fc.FLOW_MARKERS.get(e["url_class"], [])
        missing = [m for m in markers if m not in text]
        n += 1
        if missing:
            fails.append(f"{e['id']}: fixture {e['replay']} does not "
                         f"exercise class {e['url_class']} "
                         f"(missing {missing})")
    if n == 0:
        fails.append("replay: zero fixtures executed (empty-run law)")
    return fails


def live(repo: Path, target: str) -> int:
    """The live-mode law: refuse without XR_LIVE_NET=1 AND an allowlisted host."""
    if os.environ.get("XR_LIVE_NET") != "1":
        return c.skip_visible(
            "compat(live)",
            "live mode requires XR_LIVE_NET=1 (corpus contents are reviewed "
            "before any live fetch — L10-ish law; set it only on a reviewed "
            "corpus)")
    sys.path.insert(0, str(repo / "build" / "upstream"))
    from fetch import assert_url_allowed  # type: ignore
    try:
        assert_url_allowed(target)
    except Exception as exc:
        print(f"REFUSED: live corpus target {target!r} not on the fetch "
              f"allowlist ({exc}) — no hosts are added for the corpus; a "
              f"real live-fetch need is a stop-and-report")
        return c.EXIT_FAIL
    print(f"FAIL: live fetch is farm-runbook (docs/qa/compat-corpus.md); "
          f"not automated in this sandbox")
    return c.EXIT_FAIL


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="compat", description=__doc__)
    p.add_argument("--repo", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("replay")
    lp = sub.add_parser("live")
    lp.add_argument("target", help="candidate live URL (refused unless "
                                   "XR_LIVE_NET=1 and allowlisted)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        corpus = load_corpus(repo)
        if args.cmd == "validate":
            fails = validate(repo, corpus)
        elif args.cmd == "replay":
            fails = replay(repo, corpus)
        else:
            return live(repo, args.target)
    except c.RunnerError as exc:
        print(f"FAIL: {exc}")
        return c.EXIT_FAIL

    if args.json:
        print(c.stable_json({"tool": f"compat/{args.cmd}",
                             "count": len(fails), "violations": fails,
                             "status": "pass" if not fails else "fail"}))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        n = len(corpus.get("entries") or []) if args.cmd == "validate" else \
            sum(1 for e in corpus.get("entries") or []
                if e.get("mode") == "expectations-only" and e.get("replay"))
        print(f"compat {args.cmd}: {n} entr{'ies' if n != 1 else 'y'} checked, "
              f"{len(fails)} violation(s) ({'PASS' if not fails else 'FAIL'})")
    return c.EXIT_PASS if not fails else c.EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
