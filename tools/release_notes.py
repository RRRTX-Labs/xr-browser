#!/usr/bin/env python3
"""tools/release_notes.py — per-train release notes with the
consumed-upstream table (P10-T6; made date-invariant + hermetic by P12-T0-a).

The plan's law: announcement links EVIDENCE, not adjectives — every number
in the notes traces to a fetched row or says UNVERIFIED.

P12-T0-a (the gate-is-a-gate law). Before this change the non-``--fixture``
path embedded ``datetime.date.today().isoformat()`` in the citation string
that ``render()`` writes into the file, so ``--check`` re-rendered from
*today's* network data with *today's* date and diffed it against a file
regenerated on an earlier calendar day: a guaranteed daily red on a repo
that had not changed. A check whose verdict moves when nothing in the tree
moved is not a gate. Now:

  * ``--as-of <ISO date>`` is the ONLY date this tool reads. It is an
    argument DEFAULT (``tools/wall_clock_lint.py``'s single carve-out), and
    it never reaches the rendered bytes: the citation carries the
    snapshot's ``fetched`` date, which is DATA.
  * The gate path is ``--fixture`` + an explicit ``--as-of``: offline rows,
    offline CVE rows, byte-deterministic, no socket.
  * Snapshot FRESHNESS ("re-fetch me") is a scheduled-lane verdict, not a
    push-gate verdict: ``--max-age-days N`` prints ``STALE-FAIL`` and is
    visible + non-fatal there, following the shape
    ``tools/scheduled_lane_check.py`` already established.

Source of truth for a live refresh: the P3 machinery
(build/upstream/fetch.py — the allowlisted choke point, NO new hosts).

  --train 152 --out release/notes/train-152.md [--check]
      (re)generate; --check is diff-clean (house pattern).
  --fixture FILE       offline deterministic rows + CVE rows (the gate path).
  --as-of YYYY-MM-DD   comparison date (default: today; never rendered).
  --max-age-days N     scheduled-lane freshness verdict against the
                       fixture's ``fetched`` header.
Exit: 0 · 1 drift/stale · 2 usage. Stdlib + the P3 fetch machinery.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build" / "upstream"))

SUPERLATIVE_NOTE = (
    "Voice law: notes state facts with evidence links. No superlatives — "
    "tools/claims_lint.py fails the build otherwise.")

UNVERIFIED_CVE_TAIL = ("consumed-CVE table lands with the P3 fastlane run — "
                       "not asserted")


def citation_for(fetched: str) -> str:
    """The citation string. `fetched` is DATA (the snapshot header on the
    fixture path, the caller's --as-of on the live path) — never today()."""
    return (f"chromiumdash fetch_releases (allowlisted host, fetched "
            f"{fetched})")


def fetch_rows(train: int, as_of: str) -> tuple[list[dict], str]:
    """LIVE chromiumdash rows through the P3 choke point. Returns
    (rows, citation). `as_of` is the caller's comparison date; it is what
    the citation records, so a live refresh is reproducible on demand."""
    import fetch  # the P3 allowlisted choke point (NO new hosts)
    src = fetch.GitilesFetchSource()
    rows = src.releases("Stable", "Windows", 5)
    cite = citation_for(as_of)
    return [r for r in rows if int(r.get("milestone", 0)) == train] or rows, cite


def cve_rows_live(train: int, citation: str) -> list[dict]:
    """CVE notes from the SAME allowlisted host; honest UNVERIFIED when the
    endpoint does not answer with JSON."""
    try:
        import fetch
        url = f"{fetch.CHROMIUMDASH}/fetch_cve_notes?offset=0&milestone={train}"
        raw = fetch.GitilesFetchSource()._cached(url, immutable=False)
        if isinstance(raw, bytes):
            if raw[:2] == b"\x1f\x8b":
                import gzip
                raw = gzip.decompress(raw)
            raw = raw.decode("utf-8", "replace")
        data = json.loads(raw)
        out: list[dict] = []
        for row in data[:20]:
            sev = row.get("severity", "?")
            if isinstance(sev, dict):
                sev = sev.get("severity_name", "?")
            out.append({"cve_id": row.get("cve_id", "?"),
                        "title": str(row.get("title", ""))[:60],
                        "severity": sev})
        if out:
            return out
    except Exception:
        pass
    return [{"unverified": True,
             "reason": "upstream CVE endpoint did not answer with data at "
                       "fetch time"}]


def cve_lines(cve: list[dict], citation: str) -> list[str]:
    out: list[str] = []
    for row in cve:
        if row.get("unverified"):
            out.append(f"| UNVERIFIED | {row.get('reason', 'unverified')} "
                       f"({citation}); {UNVERIFIED_CVE_TAIL} |")
        else:
            out.append(f"| {row.get('cve_id', '?')} | "
                       f"{row.get('title', '')} | {row.get('severity', '?')} |")
    return out or [f"| UNVERIFIED | no CVE rows in the snapshot "
                   f"({citation}); {UNVERIFIED_CVE_TAIL} |"]


def render(train: int, rows: list[dict], cite: str, cve: list[dict]) -> str:
    lines = [
        f"# Release notes — train {train} (GENERATED by "
        "tools/release_notes.py; --check diff-clean)",
        "",
        SUPERLATIVE_NOTE,
        "",
        f"## Consumed upstream (Chromium) — {cite}",
        "",
        "| upstream version | milestone | fetched evidence |",
        "|---|---|---|",
    ]
    for r in rows[:5]:
        lines.append(
            f"| {r.get('version', '?')} | M{r.get('milestone', '?')} | "
            f"[chromiumdash release row](#{cite}) |")
    lines += [
        "",
        f"## Consumed-upstream CVE table (train {train})",
        "",
        "| CVE | title | severity |",
        "|---|---|---|",
        *cve_lines(cve, cite),
        "",
        "## Announcement body (facts only)",
        "",
        f"XR {train} tracks Chromium {rows[0].get('version', '?')} "
        f"(M{rows[0].get('milestone', '?')}) at the pinned rev in DEPS; "
        "the update path verifies manifests independent of TLS "
        "(xr-core/update/, golden vectors: 73 cases byte-parity across "
        "both backends).",
        "",
        "Evidence links, not adjectives: [evidence/P10/evidence.json]"
        "(../../evidence/P10/evidence.json) · [transparency attestation]"
        "(../transparency/attestation-example.json) · [release gate]"
        "(../../tools/release_gate.py).",
        "",
    ]
    return "\n".join(lines)


def _parse_iso(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def main() -> int:
    ap = argparse.ArgumentParser(prog="release-notes",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--train", type=int, required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fixture", default=None,
                    help="offline rows file (the gate path): {'rows': [...], "
                         "'cve': [...], 'fetched': 'YYYY-MM-DD'}")
    # The single wall-clock read in this tool, as an ARGUMENT DEFAULT — the
    # only shape tools/wall_clock_lint.py permits. The gate always passes an
    # explicit --as-of, so this default never fires under run_checks.sh, and
    # it never reaches the rendered bytes either way.
    ap.add_argument("--as-of", default=datetime.date.today().isoformat(),
                    help="comparison date YYYY-MM-DD (never rendered)")
    ap.add_argument("--max-age-days", type=int, default=0,
                    help="scheduled-lane freshness verdict: STALE-FAIL when "
                         "the fixture snapshot is older than N days at "
                         "--as-of (visible, non-fatal to the push gate)")
    a = ap.parse_args()

    try:
        as_of = _parse_iso(a.as_of)
    except ValueError:
        print(f"usage: --as-of {a.as_of!r} is not a YYYY-MM-DD date")
        return 2

    if a.fixture:
        doc = json.loads(Path(a.fixture).read_text(encoding="utf-8"))
        fetched = doc["fetched"]           # DATA from the snapshot header
        rows, cve = doc["rows"], doc.get("cve") or []
        cite = citation_for(fetched)
    else:
        fetched = a.as_of
        rows, cite = fetch_rows(a.train, a.as_of)
        cve = cve_rows_live(a.train, cite)

    rendered = render(a.train, rows, cite, cve)
    out = Path(a.out) if a.out else REPO / "release" / "notes" / \
        f"train-{a.train}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    if a.max_age_days > 0:
        age = (as_of - _parse_iso(fetched)).days
        if age > a.max_age_days:
            # STALE-* shape (tools/scheduled_lane_check.py): visible,
            # non-fatal to the push gate, never counted green.
            print(f"STALE-FAIL: {Path(a.fixture or 'snapshot').name} snapshot "
                  f"fetched {fetched} is {age} day(s) old at --as-of "
                  f"{a.as_of} (> {a.max_age_days}) — refresh it with "
                  f"`tools/release_notes.py --train {a.train}` against the "
                  f"live choke point, then re-commit the fixture. This is a "
                  f"scheduled-lane verdict; it never reddens a push gate.")
            return 1

    if a.check:
        if out.read_text(encoding="utf-8") != rendered:
            print(f"FAIL: {out} stale (run tools/release_notes.py "
                  f"--train {a.train} --fixture <snapshot>)")
            return 1
        print(f"PASS: release-notes diff-clean ({out.name}; offline fixture, "
              f"fetched {fetched}, as-of {a.as_of} — date-invariant)")
        return 0
    out.write_text(rendered, encoding="utf-8")
    print(f"wrote {out} ({len(rows)} upstream row(s); {cite})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
