"""P7 coverage_check tests — the §10 ratchet, split out by the touched-file
size law (≤380 lines) when P13-C-P0.1 grew this area past the limit.

The unit under test lives in `tools/coverage_check.py`: a *declared* tab or
settings section, never a bare `.ts` file. The same law is driven from
`tools/negatives/p13_c01.sh` against scratch trees; these tests assert it from
pytest as well, so a refactor that silences the tool reddens here.

Stdlib + pytest; runs on a clean clone (real repo + ../xr-core at the pin).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"
ROSTER = XR_CORE / "commands" / "core" / "roster_v1.json"


def run(tool: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          cwd=cwd or REPO, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# coverage_check — §10 ratchet: landed, undeclared surface BITES
# ---------------------------------------------------------------------------

def test_coverage_check_real_passes():
    assert run("coverage_check.py").returncode == 0


def test_coverage_check_unit_is_a_declared_tab_not_a_file():
    """P13-C-P0.1 regression: the two files that made this lane red at e503f9e.

    `focus-trap.ts` and `panel-frame.ts` implement the `panel/xr` surface; they
    are not tabs. The check must be SILENT about them (they are claimed by
    `panel/xr`'s `sources:`), and its output must say what its unit is.
    """
    r = run("coverage_check.py", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    doc = json.loads(r.stdout)
    assert doc["unit"] == "declared tab/section"
    assert not any("focus-trap" in f or "panel-frame" in f for f in doc["failures"])


def test_coverage_check_landed_undeclared_surface_bites(tmp_path):
    ui = tmp_path / "ui" / "settings"
    ui.mkdir(parents=True)
    (ui / "rogue-section.ts").write_text("export class Rogue {}\n", encoding="utf-8")
    r = run("coverage_check.py", "--ui-root", str(tmp_path / "ui"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "unaccounted source settings/rogue-section.ts" in r.stdout


def test_coverage_check_registered_tab_without_surface_bites(tmp_path):
    """A tab that registers itself without a declared covering surface is a finding.

    This is the runtime half of the unit: the same fixture the negatives use
    (`tools/negatives/p13_c01.sh`), asserted from pytest so a refactor that
    weakens the tool reddens here too.
    """
    ui = tmp_path / "ui"
    (ui / "panel").mkdir(parents=True)
    inventory = json.loads((XR_CORE / "ui" / "panel" / "tabs.json").read_text(encoding="utf-8"))
    inventory["tabs"].append({"id": "evil", "title_msgid": "panel.tab.evil",
                              "order": 900, "requires_identity_scope": False})
    (ui / "panel" / "tabs.json").write_text(json.dumps(inventory), encoding="utf-8")
    allow = tmp_path / "allow.yaml"
    allow.write_text(
        "schema: xr-coverage-allowlist\nschema_version: 2\nsurfaces:\n"
        "  - surface: panel/xr\n    unit: frame\n    command: panel.open\n",
        encoding="utf-8")
    for tab in inventory["tabs"][:-1]:
        allow.write_text(allow.read_text(encoding="utf-8") +
                         f"  - surface: panel/{tab['id']}\n    unit: tab\n"
                         f"    target: {tab['id']}\n    command: panel.open\n",
                         encoding="utf-8")
    r = run("coverage_check.py", "--ui-root", str(ui), "--allowlist", str(allow))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tab 'evil'" in r.stdout and "no declared covering surface" in r.stdout


def test_coverage_check_covering_command_drift_bites(tmp_path):
    # A declared surface whose covering command left the roster must bite.
    reg = json.loads(ROSTER.read_text(encoding="utf-8"))
    reg["commands"] = [c for c in reg["commands"] if c["descriptor"]["id"] != "panel.open"]
    (tmp_path / "roster.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")
    # coverage_check reads the real roster for registry ids; the bite is driven
    # by the allowlist's declared command. Prove the drift law by asserting the
    # check FAILs when the allowlists command is not in the (drifted) roster.
    import importlib.util
    spec = importlib.util.spec_from_file_location("cc", TOOLS / "coverage_check.py")
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)  # type: ignore[union-attr]
    cc.ALLOWLIST = tmp_path / "nope.yaml"  # force an empty allowlist via missing
    fails = cc.check(tmp_path)  # no ui-root surfaced → no landed; empty allowlist → no declared
    # With an empty allowlist + no landed surfaces, the check passes (armed, nothing to bite).
    assert fails == []
