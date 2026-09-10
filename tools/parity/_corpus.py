"""tools/parity/_corpus.py — shared corpus model for the P9 parity machinery.

Single place that defines how a host-pair parity corpus is shaped and how a
case is turned into a request string for BOTH backends, so the completeness
gate (tools/parity_completeness.py), the byte-parity test
(tools/tests/test_p9_parity.py) and the differential oracle
(tools/differential_fuzz.py) can never disagree on what a case means.

Corpus JSON schema (schema_version 1):
    {
      "schema_version": 1,
      "pair": "themes|settings|commands",
      "protocol": "host_protocol.md path inside xr-core",
      "provenance": "who authored this and why",
      "cases": [
        {"id": str, "method": str, "args": {...}, "expect": "ok"|"reject"},
        {"id": str, "method": str, "theme_doc": {"base": str, "overrides": {...}},
         "expect": ...},          # themes-only: expand from a built-in palette
        {"id": str, "method": str, "args": {"theme-doc": "RAW"}, "expect": ...}
      ]
    }

`args.theme-doc` is used VERBATIM as the raw theme-doc string (hostile raw
text with duplicate keys etc.). `theme_doc` (a mapping) is expanded into a
canonical doc string: built-in palette values + overrides, dumped with
sort_keys=True/compact separators — deterministic, from ui/themes/tokens.json.

Stdlib only. No wall-clock anywhere; every value is deterministic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CASE_EXPECT = ("ok", "reject")


class CorpusError(Exception):
    """Fail-closed corpus error; message is the reason."""


@dataclass
class Case:
    id: str
    method: str
    args: dict[str, Any] = field(default_factory=dict)
    expect: str = "ok"
    theme_doc: dict[str, Any] | None = None
    pad_bytes: int = 0  # themes-only: oversize-doc generator


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise CorpusError(msg)


def load_corpus(path: Path, tokens_json: Path | None = None) -> dict[str, Any]:
    """Load + validate a corpus file; return the raw dict (cases normalized)."""
    if not path.is_file():
        raise CorpusError(f"corpus file missing: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"{path}: invalid JSON ({exc})") from None
    _require(isinstance(doc, dict), f"{path}: top level must be an object")
    _require(doc.get("schema_version") == SCHEMA_VERSION,
             f"{path}: schema_version must be {SCHEMA_VERSION}")
    _require(isinstance(doc.get("pair"), str), f"{path}: pair (str) required")
    cases = doc.get("cases")
    _require(isinstance(cases, list) and cases,
             f"{path}: cases must be a non-empty list (zero-case law)")
    norm: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in cases:
        _require(isinstance(c, dict), f"{path}: each case must be an object")
        cid = c.get("id")
        _require(isinstance(cid, str) and cid, f"{path}: case id required")
        _require(cid not in seen, f"{path}: duplicate case id {cid!r}")
        seen.add(cid)
        method = c.get("method")
        _require(isinstance(method, str) and method, f"{path}: {cid}: method required")
        expect = c.get("expect", "ok")
        _require(expect in CASE_EXPECT, f"{path}: {cid}: expect must be ok|reject")
        args = c.get("args", {})
        _require(isinstance(args, dict), f"{path}: {cid}: args must be an object")
        theme_doc = c.get("theme_doc")
        _require(theme_doc is None or isinstance(theme_doc, dict),
                 f"{path}: {cid}: theme_doc must be an object")
        pad = c.get("pad_bytes", 0)
        _require(isinstance(pad, int) and pad >= 0,
                 f"{path}: {cid}: pad_bytes must be int >= 0")
        compare = c.get("compare", "byte")
        _require(compare in ("byte", "code"),
                 f"{path}: {cid}: compare must be byte|code")
        norm.append({"id": cid, "method": method, "args": dict(args),
                     "expect": expect, "theme_doc": theme_doc,
                     "pad_bytes": pad, "compare": compare})
    doc["cases"] = norm
    if tokens_json is not None and Path(tokens_json).is_file():
        doc["_tokens"] = json.loads(Path(tokens_json).read_text(encoding="utf-8"))
    return doc


def expand_theme_doc(spec: dict[str, Any], tokens: dict[str, Any]) -> str:
    """Expand a {base, overrides} theme-doc spec into a canonical doc string."""
    base = spec.get("base")
    _require(isinstance(base, str), "theme_doc.base (str) required")
    themes = tokens.get("themes")
    _require(isinstance(themes, dict) and base in themes,
             f"theme_doc.base {base!r} not a built-in theme")
    values = {k: v for k, v in themes[base].items() if k != "waivers"}
    overrides = spec.get("overrides", {})
    _require(isinstance(overrides, dict), "theme_doc.overrides must be an object")
    values.update(overrides)
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def case_to_request(cid: str, case: dict[str, Any],
                    tokens: dict[str, Any]) -> str:
    """Turn a case into the request JSON string fed to BOTH backends."""
    args = dict(case["args"])
    if case.get("theme_doc") is not None:
        args["theme-doc"] = expand_theme_doc(case["theme_doc"], tokens)
    if case.get("pad_bytes"):
        # Oversize hostile-doc generator: a valid-shaped object padded past
        # the 64 KiB cap with a huge string value (both backends refuse on
        # raw size before parsing — the value itself never matters).
        big = "x" * case["pad_bytes"]
        args["theme-doc"] = json.dumps({"text": big}, separators=(",", ":"))
    return json.dumps({"method": case["method"], "args": args},
                      separators=(",", ":"))


def methods_in_corpus(doc: dict[str, Any]) -> dict[str, int]:
    """method -> case count over a loaded corpus."""
    out: dict[str, int] = {}
    for c in doc["cases"]:
        out[c["method"]] = out.get(c["method"], 0) + 1
    return out


def protocol_methods(md_path: Path) -> list[str]:
    """Auto-discover the method set from a host_protocol.md Methods table.

    The tables use the shape `| method-name | ... |` under a `## Methods`
    heading (themes/settings/commands host_protocol.md, P8 convention). Returns
    the method names in table order; empty when no Methods table is present
    (a pair with no table is recorded by the caller, never silently skipped).
    """
    if not md_path.is_file():
        raise CorpusError(f"protocol md missing: {md_path}")
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    in_methods = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("## ") and s.lower().endswith("methods"):
            in_methods = True
            continue
        if in_methods and s.startswith("## "):
            break
        if not in_methods:
            continue
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0].strip("`")
        if first in ("", "method", "---", "args"):
            continue
        out.append(first)
    return out
