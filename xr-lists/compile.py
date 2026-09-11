#!/usr/bin/env python3
"""xr-lists/compile.py — ABP/uBO-syntax lists -> the normalized
xr-list-bundle-v1 document (P11-T3).

The compiler is the ONLY producer of bundles: every rule it emits must
pass the shield core's strict bundle grammar (xr-core/shield/core/
bundle.cc ParseBundle/ParseFilter) — a line the normalized grammar
cannot carry becomes a TYPED REFUSAL recorded in the bundle's refusal
table ({directive, reason, count}, first-occurrence order), never a
silent ignore and never a guessed normalization (§arch 4: ship only
what the pinned engine genuinely supports; everything else refuses with
a reason). The refusal reason vocabulary is closed and pinned by
tools/list_bundle_check.py; the compile vectors
(docs/contracts/vectors/xr-lists-compile-v1.json) pin every class.

v1 capability boundary (ADR-0045, docs/shield/scriptlets.md):
  * scriptlets (#%#, #$#, ##+js) — REFUSED (zero execution surface)
  * procedural cosmetic (#?#, #@?#, :has/:matches-css/:upward/…) — REFUSED
  * regex filters — REFUSED (the normalized grammar carries none)
  * filter options — only $domain= (structured domains/exclude_domains)
    and $redirect= (kind=redirect + named resource) survive; every other
    option is REFUSED (unsupported-option:<name>)
  * simple cosmetic selectors (##/#@#) — carried as INERT DATA
    (kind=cosmetic; the v1 network engine never matches them)

Deterministic: no clock, no RNG, no network. Same config + same source
bytes => same bundle bytes (canonical JSON, sorted keys).
Exit: 0 ok · 1 compile-check drift / refusal-vocabulary violation ·
2 usage. SKIP is not a state this tool can be in (pure stdlib).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# The cosmetic markers, longest-first so #@?# never mis-splits as ##.
MARKERS = ("#@?#", "#?#", "#%#", "#$#", "#@#", "##")
PROCEDURAL_OPS = (":has(", ":matches-css", ":upward(", ":nth-ancestor",
                  ":nth-ancestor(", ":remove(", ":-abp-", ":style(")
# Refusal reasons that pin a dynamic family (prefix match); everything
# else is a literal token. tools/list_bundle_check.py pins this table.
REFUSAL_FAMILIES = ("unsupported-option:",)
REFUSAL_TOKENS = frozenset({
    "unsupported-directive:scriptlet",
    "unsupported-directive:procedural-cosmetic",
    "unsupported-directive:preprocessor",
    "unsupported-directive:regex",
    "unsupported-directive:cosmetic-hash",
    "unsupported-directive:at-syntax",
    "unsupported-directive:interior-pipe",
    "unsupported-directive:empty-segment",
    "unsupported-option-combination:redirect-on-exception",
    "malformed-option:domain",
    "malformed-option:redirect",
    "malformed-option:empty-name",
    "empty-filter",
    "malformed-line",
})


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def refusal(line: str, reason: str) -> dict:
    return {"kind": "refusal", "directive": line.strip(), "reason": reason}


def filter_grammar_refusal(filt: str) -> str | None:
    """Mirror of bundle.cc ParseFilter's refusal table (same tokens, same
    order) — the compiler refuses HERE so a compiled bundle can never be
    refused at load (a compile leak is a bug, not a fallback)."""
    if not filt:
        return "empty-filter"
    if filt[0] == "!":
        return "unsupported-directive:comment"
    if len(filt) >= 2 and filt[0] == "/" and filt[-1] == "/":
        return "unsupported-directive:regex"
    if "$" in filt:
        return "unsupported-directive:options-in-filter"
    if "#" in filt:
        return "unsupported-directive:cosmetic-hash"
    if "@" in filt:
        return "unsupported-directive:at-syntax"
    body = filt
    if body.startswith("||"):
        body = body[2:]
    elif body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    if "|" in body:
        return "unsupported-directive:interior-pipe"
    if not body:
        return "empty-filter"
    segs: list[str] = []
    cur = ""
    for c in body:
        if c == "*":
            if cur or not segs:
                segs.append(cur)
            cur = ""
            continue
        cur += c
    segs.append(cur)
    for s in segs[1:-1]:
        if not s:
            return "unsupported-directive:empty-segment"
    return None


def split_domains(value: str) -> tuple[list[str], list[str]] | None:
    inc, exc = [], []
    for entry in value.split("|"):
        if not entry:
            return None
        if entry.startswith("~"):
            if len(entry) == 1:
                return None
            exc.append(entry[1:])
        else:
            inc.append(entry)
    if not inc and not exc:
        return None
    return inc, exc


def split_cosmetic_domains(lhs: str) -> tuple[list[str], list[str]] | None:
    """ABP cosmetic scoping is COMMA-separated (a.com,~b.com##sel)."""
    inc, exc = [], []
    for entry in lhs.split(","):
        entry = entry.strip()
        if not entry:
            return None
        if entry.startswith("~"):
            if len(entry) == 1:
                return None
            exc.append(entry[1:])
        else:
            inc.append(entry)
    if not inc and not exc:
        return None
    return inc, exc


def parse_cosmetic(line: str, lhs: str, rhs: str,
                   action: str) -> list[dict]:
    """lhs = domain scoping before the marker, rhs = the selector; the
    refusal directive text is always the FULL source line."""
    if rhs.startswith("+js(") or rhs.startswith("//scriptlet"):
        return [refusal(line, "unsupported-directive:scriptlet")]
    if any(op in rhs for op in PROCEDURAL_OPS):
        return [refusal(line, "unsupported-directive:procedural-cosmetic")]
    bad = filter_grammar_refusal(rhs)
    if bad:
        return [refusal(line, bad)]
    out: dict[str, Any] = {"kind": "rule", "action": action, "filter": rhs,
                           "kind_": "cosmetic"}
    if lhs:
        dom = split_cosmetic_domains(lhs)
        if dom is None:
            return [refusal(line, "malformed-option:domain")]
        if dom[0]:
            out["domains"] = dom[0]
        if dom[1]:
            out["exclude_domains"] = dom[1]
    return [out]


def parse_network(line: str) -> list[dict]:
    filt = line
    exception = False
    if filt.startswith("@@"):
        exception = True
        filt = filt[2:]
    opts_raw = ""
    if "$" in filt:
        filt, opts_raw = filt.split("$", 1)
    domains: list[str] = []
    excludes: list[str] = []
    redirect_to = ""
    refusals: list[dict] = []
    if opts_raw != "" or "$" in line:
        for opt in opts_raw.split(","):
            name, _, value = opt.partition("=")
            if not name:
                refusals.append(refusal(line, "malformed-option:empty-name"))
                continue
            if name == "domain":
                if not value:
                    refusals.append(refusal(line, "malformed-option:domain"))
                    continue
                dom = split_domains(value)
                if dom is None:
                    refusals.append(refusal(line, "malformed-option:domain"))
                    continue
                domains.extend(dom[0])
                excludes.extend(dom[1])
            elif name == "redirect":
                if exception:
                    refusals.append(refusal(
                        line, "unsupported-option-combination:"
                              "redirect-on-exception"))
                elif not value:
                    refusals.append(refusal(line,
                                            "malformed-option:redirect"))
                else:
                    redirect_to = value
            else:
                refusals.append(refusal(line, f"unsupported-option:{name}"))
    if refusals:
        return refusals  # a line with ANY refused option is refused whole
    bad = filter_grammar_refusal(filt)
    if bad:
        return [refusal(line, bad)]
    if redirect_to:
        return [{"kind": "rule", "action": "redirect", "filter": filt,
                 "kind_": "redirect", "resource": redirect_to,
                 **({"domains": domains} if domains else {}),
                 **({"exclude_domains": excludes} if excludes else {})}]
    out: dict[str, Any] = {"kind": "rule",
                           "action": "allow" if exception else "block",
                           "filter": filt, "kind_": "network"}
    if domains:
        out["domains"] = domains
    if excludes:
        out["exclude_domains"] = excludes
    return [out]


def parse_line(line: str) -> list[dict]:
    """One source line -> [] (skip), [rule], or [refusal, …] (typed)."""
    s = line.strip()
    if not s:
        return []
    if s.startswith("!#"):
        return [refusal(s, "unsupported-directive:preprocessor")]
    if s.startswith("!"):
        return []  # ABP comment — stripped, not refused (README)
    if s.startswith("[") and s.endswith("]"):
        return []  # list header ([Adblock Plus 2.0]) — metadata
    for marker in MARKERS:
        idx = s.find(marker)
        if idx >= 0:
            lhs, rhs = s[:idx], s[idx + len(marker):]
            if marker in ("#%#", "#$#"):
                return [refusal(s, "unsupported-directive:scriptlet")]
            if marker in ("#@?#", "#?#"):
                return [refusal(s,
                                "unsupported-directive:procedural-cosmetic")]
            return parse_cosmetic(s, lhs, rhs,
                                  "allow" if marker == "#@#" else "block")
    return parse_network(s)


def compile_list(name: str, attribution: str, text: str) -> tuple[dict, list]:
    rules: list[dict] = []
    refusals: list[dict] = []
    for line in text.splitlines():
        for outcome in parse_line(line):
            if outcome["kind"] == "rule":
                rid = f"{name}-{len(rules):05d}"
                r = {"action": outcome["action"], "filter": outcome["filter"],
                     "id": rid, "kind": outcome["kind_"]}
                for opt in ("domains", "exclude_domains", "resource"):
                    if opt in outcome:
                        r[opt] = outcome[opt]
                rules.append(r)
            else:
                refusals.append({"directive": outcome["directive"],
                                 "reason": outcome["reason"]})
    return {"name": name, "attribution": attribution, "rules": rules}, \
        refusals


def compile_config(cfg_path: Path) -> dict:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if set(cfg) != {"bundle_name", "bundle_version", "lists"}:
        raise SystemExit(f"FAIL: config {cfg_path.name}: keys must be "
                         "exactly bundle_name/bundle_version/lists")
    if not isinstance(cfg["bundle_version"], int) or \
            cfg["bundle_version"] <= 0:
        raise SystemExit("FAIL: bundle_version must be a positive int")
    lists, refusals = [], []
    for entry in cfg["lists"]:
        if set(entry) != {"name", "path", "attribution"}:
            raise SystemExit(f"FAIL: list entry keys must be exactly "
                             f"name/path/attribution: {entry}")
        text = (cfg_path.parent / entry["path"]).read_text(encoding="utf-8")
        lst, refs = compile_list(entry["name"], entry["attribution"], text)
        lists.append(lst)
        refusals.extend(refs)
    # aggregate identical (directive, reason) pairs; first-occurrence order
    agg: list[dict] = []
    index: dict[tuple, int] = {}
    for r in refusals:
        key = (r["directive"], r["reason"])
        if key in index:
            agg[index[key]]["count"] += 1
        else:
            index[key] = len(agg)
            agg.append({**r, "count": 1})
    return {"schema": "xr-list-bundle", "schema_version": 1,
            "name": cfg["bundle_name"],
            "bundle_version": cfg["bundle_version"], "lists": lists,
            "refusals": agg}


def main() -> int:
    ap = argparse.ArgumentParser(prog="xr-lists/compile.py")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None, help="write the bundle here")
    ap.add_argument("--check", default=None,
                    help="byte-compare the regeneration against this file")
    a = ap.parse_args()
    cfg_path = Path(a.config).resolve()
    if not cfg_path.exists():
        print(f"FAIL: config not found: {cfg_path}")
        return 2
    if bool(a.out) == bool(a.check):
        print("FAIL: exactly one of --out / --check")
        return 2
    bundle = compile_config(cfg_path)
    blob = canonical(bundle) + "\n"
    if a.check:
        got = Path(a.check).read_text(encoding="utf-8")
        if got != blob:
            print(f"DRIFT: {a.check} does not match regeneration from "
                  f"{cfg_path.name} — run xr-lists/compile.py")
            return 1
        n_ref = sum(r["count"] for r in bundle["refusals"])
        print(f"PASS: {Path(a.check).name} regenerates byte-identical "
              f"({len(bundle['lists'])} lists, "
              f"{sum(len(l['rules']) for l in bundle['lists'])} rules, "
              f"{len(bundle['refusals'])} refusal entries / {n_ref} lines)")
        return 0
    Path(a.out).write_text(blob, encoding="utf-8")
    print(f"wrote bundle -> {a.out} ({len(bundle['refusals'])} refusals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
