"""P8-T5 l10n tooling tests: grdp_check (strict xr_strings.grdp validator)
and l10n_extract (raw user-visible string lint + id cross-check).

Stdlib + pytest; runs on the real repo (uses ../xr-core). No positive test
pins the live tree state with a NUMBER any more: P13-C-P0.1c removed the last
one (see test_real_grdp_passes_strict_gate). The count law is derived-vs-derived
plus a grow-only ratchet in docs/qa/l10n-ratchet.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"
GRDP = XR_CORE / "l10n" / "xr_strings.grdp"
CARD = XR_CORE / "l10n" / "isolation_card.json"

GRIT_HEAD = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <grit-part>
""")


def grit(*msgs: str) -> str:
    return GRIT_HEAD + "\n".join(msgs) + "\n</grit-part>\n"


def msg(name: str, xr_id: str, body: str, desc: str = "desc") -> str:
    return (f'<message name="{name}" xr-id="{xr_id}" desc="{desc}">'
            f"{body}</message>")


def run(tool: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          cwd=cwd or REPO, capture_output=True, text=True)


# ---------------------------------------------------------------- grdp_check

RATCHET = REPO / "docs" / "qa" / "l10n-ratchet.json"


def _count_law():
    """The derived-count law module (P13-C-P0.1c), imported not re-implemented."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("lcl", TOOLS / "l10n_count_law.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_real_grdp_passes_strict_gate() -> None:
    """The tool is green AND its own words agree with the file.

    This used to read `assert "OK (127 messages" in r.stdout  # P11-T6: +36
    shield; P12-T6: +14 cosmetic` — a number copied out of a transcript into an
    assertion, with a comment tracking which phase last bumped it. At the pin
    the tool reported 136 while the literal still said 127: three phases had
    edited it and P13 had not. Refreshing the number would reproduce the defect
    with a fresher number, so the comparison is now DERIVED vs DERIVED — the
    count the tool printed, against an independent count of `<message>` elements
    in the same file. A disagreement fails; nothing here needs editing when a
    phase adds a string.
    """
    r = run("grdp_check.py", "--ids-from-schema")
    assert r.returncode == 0, r.stderr
    law = _count_law()
    derived = law.independent_count(GRDP)
    reported = law.reported_count(r.stdout)
    assert reported is not None, f"the tool printed no count line: {r.stdout!r}"
    assert reported == derived, (
        f"grdp_check reported {reported} messages; the file carries {derived}")


def test_grdp_count_is_above_the_grow_only_ratchet() -> None:
    """Decrease detection lives in a ratchet FILE, not in a test literal.

    Shape precedent: P8's `ratchet: "916 (grow-only)"` row in perf-budgets.json.
    Raising the floor is a reviewed act that shows up in the diff; adding a
    string needs no edit at all.
    """
    law = _count_law()
    doc = json.loads(RATCHET.read_text(encoding="utf-8"))
    derived = law.independent_count(GRDP)
    assert derived >= doc["messages"], (
        f"{GRDP.name} holds {derived} messages, below the grow-only ratchet "
        f"{doc['messages']} ({RATCHET})")
    assert doc["direction"] == "grow-only"


def test_count_law_reddens_on_a_stale_transcript(tmp_path: Path) -> None:
    """The registered negative, asserted here too: a `.grdp` with an extra
    message while the tool reports the old count is a FAILURE, not a pass."""
    law = _count_law()
    body = GRDP.read_text(encoding="utf-8")
    extra = '<message name="IDS_XR_T_EXTRA" desc="extra" xr-id="t.extra">X</message>\n'
    grown = tmp_path / "grown.grdp"
    grown.write_text(body.replace("</grit-part>", extra + "</grit-part>"), encoding="utf-8")
    stale = f"grdp_check: xr_strings.grdp OK ({law.independent_count(GRDP)} messages, isolation-card cross-check clean)\n"
    fails = law.check(grown, stale, None)
    assert fails and "but the tool reported" in fails[0], fails
    # ...and the same pair, in agreement, passes (so the negative is not
    # "everything reddens").
    fresh = f"grdp_check: xr_strings.grdp OK ({law.independent_count(grown)} messages, ok)\n"
    assert law.check(grown, fresh, None) == []


def test_grdp_name_xrid_mismatch_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(grit(msg("IDS_XR_T_ONE", "t.two", "Hello")))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "does not match xr-id" in r.stderr


def test_grdp_missing_desc_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(GRIT_HEAD + '<message name="IDS_XR_T_ONE" xr-id="t.one">'
                 "Hi</message>\n</grit-part>\n")
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "missing desc" in r.stderr


def test_grdp_ph_program_text_mismatch_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(grit(
        '<message name="IDS_XR_T_KEY" xr-id="t.key" desc="d">Key is '
        '<ph name="KEY">{VALUE}<ex>7</ex></ph></message>'))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "program text must be exactly" in r.stderr


def test_grdp_undeclared_token_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(grit(msg("IDS_XR_T_KEY", "t.key", "Key {KEY} is set")))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "no <ph> declaration" in r.stderr


def test_grdp_duplicate_ph_name_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(grit(
        '<message name="IDS_XR_T_KEY" xr-id="t.key" desc="d">Key set '
        '<ph name="KEY">{KEY}<ex>7</ex></ph> twice '
        '<ph name="KEY">{KEY}<ex>7</ex></ph></message>'))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "duplicate <ph name>" in r.stderr


def test_grdp_vocab_banned_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(grit(msg("IDS_XR_T_KEY", "t.key", "stealth mode off")))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "vocab-lint banned term" in r.stderr


def test_grdp_bidi_control_refused(tmp_path: Path) -> None:
    p = tmp_path / "bad.grdp"
    p.write_text(grit(msg("IDS_XR_T_KEY", "t.key", "evil \u202e override")))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "bidi control" in r.stderr


def test_grdp_schema_coverage_fails_on_missing_section(tmp_path: Path) -> None:
    p = tmp_path / "partial.grdp"
    # valid file, but none of the 3 schema section titles present
    p.write_text(grit(msg("IDS_XR_T_ONE", "t.one", "Hello")))
    r = run("grdp_check.py", "--grdp", str(p), "--ids-from-schema")
    assert r.returncode == 1
    assert "settings.section.network" in r.stderr


def test_grdp_isolation_card_redefinition_refused(tmp_path: Path) -> None:
    card = json.loads(CARD.read_text(encoding="utf-8"))
    sid = next(iter(card["strings"]))
    name = "IDS_XR_" + sid.upper().replace(".", "_").replace("-", "_")
    p = tmp_path / "bad.grdp"
    p.write_text(grit(msg(name, sid, "cloned card text")))
    r = run("grdp_check.py", "--grdp", str(p))
    assert r.returncode == 1
    assert "redefined in the grdp" in r.stderr


def test_grdp_self_heals_from_schema_drift() -> None:
    """Any schema id removed from the grdp turns the gate red."""
    import re as _re
    body = GRDP.read_text(encoding="utf-8")
    body = _re.sub(r'<message name="IDS_XR_SETTINGS_SECTION_NETWORK".*?'
                   r"</message>", "", body, count=1, flags=_re.S)
    p = Path(GRDP).parent / ".test-drift.grdp"
    p.write_text(body)
    try:
        r = run("grdp_check.py", "--grdp", str(p), "--ids-from-schema")
        assert r.returncode == 1
        assert "settings.section.network" in r.stderr
    finally:
        p.unlink()


# --------------------------------------------------------------- l10n_extract

def test_real_tree_extract_clean() -> None:
    r = run("l10n_extract.py", "--check")
    assert r.returncode == 0, r.stderr
    assert "CLEAN" in r.stdout


def test_extract_flags_raw_text_node(tmp_path: Path) -> None:
    fake = tmp_path / "ui"
    fake.mkdir(parents=True)
    (fake / "x.ts").write_text(
        "import { html } from 'lit';\n"
        "export const X = () => html`<p>Raw visible words here.</p>`;\n")
    r = run("l10n_extract.py", "--xr-core", str(tmp_path), "--grdp", str(GRDP))
    assert r.returncode == 1
    assert "R1" in r.stderr and "Raw visible words" in r.stderr


def test_extract_flags_raw_aria_literal(tmp_path: Path) -> None:
    fake = tmp_path / "ui"
    fake.mkdir(parents=True)
    (fake / "x.ts").write_text(
        "import { html } from 'lit';\n"
        'export const X = () => html`<button aria-label="Close panel">x</button>`;\n')
    r = run("l10n_extract.py", "--xr-core", str(tmp_path), "--grdp", str(GRDP))
    assert r.returncode == 1
    assert "R2" in r.stderr and "Close panel" in r.stderr


def test_extract_code_tokens_allowed(tmp_path: Path) -> None:
    fake = tmp_path / "ui"
    fake.mkdir(parents=True)
    (fake / "x.ts").write_text(
        "import { html } from 'lit';\n"
        "const a = 'xr-palette-list';\n"
        "const b = 'ArrowDown';\n"
        "const c = 'palette.command-label';\n"
        "const d = 'https://example.com/x';\n"
        "const e = '';\n"
        "export const X = html`<p>${a}</p>`;\n")
    r = run("l10n_extract.py", "--xr-core", str(tmp_path), "--grdp", str(GRDP))
    assert r.returncode == 0, r.stderr


def test_extract_missing_referenced_id(tmp_path: Path) -> None:
    fake = tmp_path / "ui"
    fake.mkdir(parents=True)
    (fake / "x.ts").write_text(
        "import { text } from '../i18n.js';\n"
        "export const X = (m) => html`<p>${text(m, 't.nothere')}</p>`;\n")
    r = run("l10n_extract.py", "--xr-core", str(tmp_path), "--grdp", str(GRDP))
    assert r.returncode == 1
    assert "'t.nothere'" in r.stderr
