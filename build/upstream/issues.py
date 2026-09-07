"""build/upstream/issues.py — conflict routing (P3-T2): per failed patch,
prepare an owner-routed issue bundle (Plan §12.1: "Conflicts ⇒ auto-issue to
owning team with context"; §4 P3-T2).

Vocabulary law: until hosted filing is human-gated ON (HG-16), this tool
"PREPARES ISSUE BUNDLES" — it never claims to file anything. Default mode is
files-only (CI mode). Hosted mode (XR_ISSUES_TARGET=github) additionally
emits a ready-to-run `gh-commands.sh` script; the bot itself reads NO
credentials and performs NO writes anywhere (fetch is read-only; this module
only writes bundle files under the output directory).

Redaction (phase Security req): generated markdown strips emails and absolute
user paths — regex-enforced and test-covered. No secrets exist in this
pipeline; the bundle contains only upstream-public data + manifest metadata.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard  # noqa: E402
from classify import (  # noqa: E402
    CLASS_DELETED, CLASS_DRIFT, CLASS_MOVED, CLASS_SEMANTIC, CLASS_STALE_BASE,
    PatchResult,
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ABSPATH_RE = re.compile(r"(?<![\w.])/(?:home|Users|root|tmp)/[^\s`\"')\]]*")

RECLASS = {
    CLASS_DRIFT: "re-run the 3-way merge and re-anchor hunks (mechanical)",
    CLASS_MOVED: "re-point the patch at the new path (mechanical re-anchor)",
    CLASS_SEMANTIC: "resolve in PATCH SEMANTICS — never disable/drop the hook "
                    "(§12.3); if it cannot be carried, retire it with a "
                    "user-visible consequence + review entry",
    CLASS_DELETED: "upstream deleted the target — retirement review required "
                   "(§12.3) or re-anchor onto the successor surface",
    CLASS_STALE_BASE: "the manifest/patch pair is inconsistent at its own pin — "
                      "fix the manifest before the next rebase run",
}

_CONFLICT_CLASSES = {CLASS_DRIFT, CLASS_MOVED, CLASS_SEMANTIC,
                     CLASS_DELETED, CLASS_STALE_BASE}


def redact(text: str) -> str:
    """Strip emails and absolute user paths from generated markdown."""
    text = _EMAIL_RE.sub("<redacted-email>", text)
    text = _ABSPATH_RE.sub("<redacted-path>", text)
    return text


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_bundle(patch: PatchResult, *, from_rev: str, to_rev: str,
                 source: str, range_log: list[dict[str, Any]] | None = None,
                 per_file_context: dict[str, dict[str, str]] | None = None) -> str:
    """Render the routed markdown bundle for one non-clean patch."""
    per_file_context = per_file_context or {}
    lines = [
        f"# [XR-REBASE] patch `{patch.id}` needs owner action ({patch.cls})",
        "",
        f"- **Owner (from manifest):** {patch.owner}",
        f"- **Classification:** `{patch.cls}`",
        f"- **Category:** {patch.category} (patch budget class, §1.2)",
        f"- **Range:** `{from_rev[:12]}…` → `{to_rev[:12]}…` ({'fixture' if source == 'fixture' else 'real upstream'} data)",
        f"- **Generated:** {_now_iso()}Z",
        f"- **Suggested action:** {RECLASS.get(patch.cls, 'triage')}",
        "",
        "## Files",
    ]
    for f in patch.files:
        lines.append(f"### `{f.path}` — {f.cls}")
        if f.moved_to:
            lines.append(f"- identical content now at `{f.moved_to}` (re-anchor candidate)")
        if f.detail:
            lines.append(f"- {f.detail}")
        ctx = per_file_context.get(f.path, {})
        if ctx.get("pin") is not None or ctx.get("target") is not None:
            lines += ["", "```diff",
                      f"--- pin ({from_rev[:12]})", f"+++ target ({to_rev[:12]})", "```"]
    lines += ["", "## Upstream context (range log, newest first)", ""]
    if range_log:
        lines.append("Path-scoped last-touch attribution is not anonymously "
                     "available on gitiles (403, research log R1); the range "
                     "log below is the public context of record.")
        for c in range_log[:10]:
            sha = c.get("commit", "?")[:12]
            when = c.get("committer", {}).get("time", "?")
            subject = c.get("message", "").splitlines()[0] if c.get("message") else "?"
            lines.append(f"- `{sha}` {when} — {subject}")
    else:
        lines.append("- (no range log available for this run)")
    lines += [
        "",
        "## Rules of engagement",
        "",
        "- Resolve in **patch semantics**; `disable & TODO` is forbidden (§12.3).",
        "- Patch changes go through the xr-patch machinery / ledger, never ad-hoc edits (L10).",
        "- This bundle was prepared by a read-only bot; a human applies and reviews.",
    ]
    return redact("\n".join(lines)) + "\n"


def route(report: dict, out_dir: Path, *, hosted: bool = False) -> list[Path]:
    """Write one bundle per non-clean patch row of a rebase-report; return paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for p in report.get("patches", []):
        if p.get("cls") not in _CONFLICT_CLASSES:
            continue
        patch = PatchResult(id=p["id"], owner=p.get("owner", "?"),
                            category=p.get("category", "?"), cls=p["cls"],
                            files=[type("F", (), {"path": f["path"], "cls": f["cls"],
                                                  "detail": f.get("detail", ""),
                                                  "moved_to": f.get("moved_to")})() for f in p.get("files", [])])
        body = build_bundle(patch, from_rev=report.get("from_rev", "?"),
                            to_rev=report.get("to_resolved", report.get("to_rev", "?")),
                            source=report.get("source", "?"),
                            range_log=report.get("range_log"))
        path = out_dir / f"{stamp}-{p['id']}.md"
        path.write_text(body, encoding="utf-8")
        written.append(path)
    if hosted:
        script = ["#!/bin/sh",
                  "# Prepared by xr-issues (files mode + hosted command script).",
                  "# Execution is a HUMAN act (HG-16): review every bundle, then run.",
                  "# Requires: gh CLI authenticated with repo Issues:write (research R6).",
                  "set -eu"]
        for b in written:
            script.append(f'gh issue create --repo "$XR_ISSUE_REPO" '
                          f'--title "XR-REBASE: {b.stem.split("-", 5)[-1]} needs owner action" '
                          f'--body-file "{b}" --label "rebase,xr-upstream"')
        (out_dir / "gh-commands.sh").write_text("\n".join(script) + "\n", encoding="utf-8")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-issues",
        description="Prepare owner-routed issue bundles from a rebase-report "
                    "(files mode; hosted mode emits a gh command script, never executes it).")
    parser.add_argument("--report", required=True, help="rebase-report.json path")
    parser.add_argument("--out", default="work/upstream-cache/issues",
                        help="bundle output directory")
    args = parser.parse_args()

    import json
    try:
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ToolError(f"cannot read report {args.report}: {exc}") from exc

    hosted = bool(__import__("os").environ.get("XR_ISSUES_TARGET") == "github")
    written = route(report, Path(args.out), hosted=hosted)
    for w in written:
        print(f"bundle: {w}")
    if hosted:
        print(f"hosted command script: {Path(args.out) / 'gh-commands.sh'} "
              "(NOT executed — HG-16 human gate)")
    print(f"{len(written)} bundle(s) prepared")
    return 0


if __name__ == "__main__":
    main_with_guard(lambda: main())
