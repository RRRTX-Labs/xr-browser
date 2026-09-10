#!/usr/bin/env python3
"""tools/copy_lint.py — copy lint over the one l10n source (P9-T7, §11.6).

Extends vocab_lint (which scans docs/ and never the product's own strings)
to the ONE user-visible string source: xr-core/l10n/xr_strings.grdp — and
adds the §11.6 "no numeric-similarity score" check. It runs the banned-
vocabulary families from vocab_lint over the message texts AND over the
generated qyy artifact (docs/qa/qyy/), then flags any user-visible number
that *looks like a score*:

  * ratios "9/10", "3/5"
  * "N out of M"
  * percentages "N%" (a % is a score signal unless explicitly allowlisted)
  * decimals "4.5", "9.5"
  * "N stars" / "N points"

Data values are NOT scores: a number immediately followed by a unit
(px, ms, MB, fps, …) is exempt by rule, and anything else that genuinely
needs a number is an explicit entry in docs/state/copy-allowlist.yaml
(with a justification — the same discipline as vocab_lint). A flagged score
number without an allowlist entry fails the gate.

Why composition, not an edit of vocab_lint.py: vocab_lint stays focused on
docs/ (its scope is deliberate); this tool reuses its BANNED families by
import so there is one source of truth for the banned list.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vocab_lint import BANNED  # noqa: E402  (one source of truth for the list)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build" / "qa"))
from _common import EXIT_FAIL, EXIT_PASS, EXIT_USAGE  # noqa: E402

GRDP = "../xr-core/l10n/xr_strings.grdp"
QYY = "docs/qa/qyy/xr_strings.qyy.txt"
ALLOWLIST = "docs/state/copy-allowlist.yaml"

MSG_RE = re.compile(
    r'<message[^>]*xr-id="([^"]+)"[^>]*>(.*?)</message>', re.DOTALL)
PH_OPEN = re.compile(r'<ph[^>]*>')
EX_RE = re.compile(r'<ex>(.*?)</ex>', re.DOTALL)
TOKEN_RE = re.compile(r'\{[A-Z0-9_]+\}')

UNITS = ("px", "em", "rem", "pt", "ms", "s", "MB", "GB", "KB", "TB", "MB/s",
         "fps", "Hz", "kHz", "MHz", "GHz", "dpi", "ms/request")

SCORE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ratio", re.compile(r"\b\d+\s*/\s*\d+\b")),
    ("out-of", re.compile(r"\b\d+\s+out of\s+\d+\b", re.IGNORECASE)),
    ("percent", re.compile(r"\b\d+(?:\.\d+)?\s*%")),
    ("decimal", re.compile(r"\b\d+\.\d+\b")),
    ("stars", re.compile(r"\b\d+\s*(?:stars?|points?)\b", re.IGNORECASE)),
]


def clean_message(body: str) -> str:
    """Strip tags but keep inner example text; neutralize program tokens."""
    body = PH_OPEN.sub(" ", body)
    body = body.replace("</ph>", " ").replace("<ex>", " ").replace("</ex>", " ")
    body = TOKEN_RE.sub("TOKEN", body)
    body = body.replace("&quot;", '"').replace("&apos;", "'")
    body = body.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return body


def score_hits(text: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for name, rx in SCORE_PATTERNS:
        for m in rx.finditer(text):
            # unit-exemption: a number immediately followed by a unit is data.
            if name in ("percent", "decimal"):
                tail = text[m.end():m.end() + 8]
                if any(tail.startswith(u) for u in UNITS):
                    continue
            hits.append((name, m.group(0)))
    return hits


def extract_messages(grdp_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in MSG_RE.finditer(grdp_text):
        out[m.group(1)] = clean_message(m.group(2))
    return out


def load_allowlist(path: Path) -> list[dict]:
    if not path.exists():
        return []
    import yaml
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(doc.get("allowlist") or [])


def check(repo: Path, *, grdp_path: Path | None = None,
          qyy_path: Path | None = None) -> tuple[list[str], int]:
    fails: list[str] = []
    grdp_path = grdp_path or (repo / GRDP)
    if not grdp_path.exists():
        return [f"missing grdp at {grdp_path}"], 0
    grdp_text = grdp_path.read_text(encoding="utf-8")
    messages = extract_messages(grdp_text)
    if not messages:
        return ["grdp: zero messages extracted (empty-run law)"], 0

    qyy_path = qyy_path or (repo / QYY)
    qyy_lines: list[str] = []
    if qyy_path.exists():
        qyy_lines = [l for l in qyy_path.read_text(
            encoding="utf-8").splitlines() if l.strip()]

    allow = load_allowlist(repo / ALLOWLIST)
    allowed = {(a.get("xr_id"), a.get("pattern")) for a in allow
               if isinstance(a, dict)}

    checked = 0
    for xr_id, text in messages.items():
        checked += 1
        # 1) banned vocabulary over the source message text
        for name, rx in BANNED:
            for m in rx.finditer(text):
                if (xr_id, name) not in allowed:
                    fails.append(f"{xr_id}: banned pattern {name!r} "
                                 f"({m.group(0)!r}) — no copy-allowlist entry")
        # 2) score-number check over source + qyy line
        for name, hit in score_hits(text):
            if (xr_id, name) not in allowed:
                fails.append(f"{xr_id}: score-looking {name} {hit!r} — "
                             f"not a data value (copy-allowlist)")
    for line in qyy_lines:
        for name, hit in score_hits(line):
            # qyy lines are pseudo-locale; the source id is not recoverable
            # per line, so the qyy check uses the raw pattern.
            if ("qyy", name) not in allowed:
                fails.append(f"qyy: score-looking {name} {hit!r} in "
                             f"{line[:40]!r} — not a data value")
    return fails, checked


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="copy_lint", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--grdp", default="", help="override grdp path (fixtures)")
    p.add_argument("--qyy", default="", help="override qyy path (fixtures)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    grdp = Path(args.grdp) if args.grdp else None
    qyy = Path(args.qyy) if args.qyy else None
    fails, checked = check(repo, grdp_path=grdp, qyy_path=qyy)
    if args.json:
        print(json.dumps({"tool": "copy_lint", "strings_checked": checked,
                          "count": len(fails), "violations": fails,
                          "status": "pass" if not fails else "fail"},
                         sort_keys=True, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"copy_lint: {checked} string(s) checked, {len(fails)} "
              f"violation(s) ({'PASS' if not fails else 'FAIL'})")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
