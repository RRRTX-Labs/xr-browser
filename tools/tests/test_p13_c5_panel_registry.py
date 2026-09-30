"""P13-T6 / C-5: the panel tab registry lane (tools/panel_registry_check.py).

The contract (`panel-tab-registration-v1`) is the thing that makes a panel tab a
DECLARED unit. Its runtime half is xr-core's `ui/panel/tab-registry.ts` (typed
refusals, proven by its node suite inside build/webui/panel-tests.sh); this file
proves the GATE half, which is the half that can be weakened by an edit to a
JSON file:

  * the inventory validates against the schema, and the vector file is EXECUTED
    (a corrupted accept payload must redden — a vector file nothing runs is
    prose);
  * gating the §10 claim: a declared tab with no `sources:` line is a
    placeholder, and a `skip:` key is not a claim;
  * the BYPASS law: a frame that names a tab id as a literal has stopped being
    registry-driven, and the lane must say which id and which file.

Runs against the real repo + ../xr-core (the pin lane is a separate gate; these
tests exist to prove the RULES, so the fixtures use --ui-root/--allowlist, the
same fixture overrides tools/coverage_check.py already exposes).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"
TOOL = TOOLS / "panel_registry_check.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, cwd=str(REPO))


def _repo_copy(tmp_path: Path) -> Path:
    """A scratch repo with the three files the lane reads. Never the real tree:
    a test that writes into the checkout dirtying the sibling is the P13-C-P0.2c
    defect, and the pin lane refuses to run on a dirty tree."""
    repo = tmp_path / "repo"
    (repo / "docs/contracts/vectors").mkdir(parents=True)
    shutil.copy(REPO / "docs/contracts/panel-tab-registration-v1.schema.json",
                repo / "docs/contracts/panel-tab-registration-v1.schema.json")
    shutil.copy(REPO / "docs/contracts/vectors/panel-tab-registration-v1.json",
                repo / "docs/contracts/vectors/panel-tab-registration-v1.json")
    shutil.copy(REPO / "docs/contracts/coverage-allowlist.yaml",
                repo / "docs/contracts/coverage-allowlist.yaml")
    return repo


def _core_copy(tmp_path: Path) -> Path:
    """A scratch xr-core with the ui/ tree and the grdp."""
    core = tmp_path / "core"
    shutil.copytree(XR_CORE / "ui", core / "ui")
    (core / "l10n").mkdir()
    shutil.copy(XR_CORE / "l10n" / "xr_strings.grdp", core / "l10n" / "xr_strings.grdp")
    return core


def test_lane_passes_on_the_real_tree():
    r = run("--repo", str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS: panel_registry_check" in r.stdout


def test_the_real_inventory_is_what_the_allowlist_claims():
    """The claim law's positive half: every declared tab names its file."""
    inventory = json.loads((XR_CORE / "ui/panel/tabs.json").read_text(encoding="utf-8"))
    import yaml

    allow = yaml.safe_load((REPO / "docs/contracts/coverage-allowlist.yaml")
                           .read_text(encoding="utf-8"))["surfaces"]
    by_tab = {a["target"]: a for a in allow if a.get("unit") == "tab"}
    for tab in inventory["tabs"]:
        entry = by_tab[tab["id"]]
        assert entry.get("sources"), f"{tab['id']} claims no sources"
        for src in entry["sources"]:
            assert (XR_CORE / "ui" / src).exists(), f"{src} does not exist"


def test_a_frame_that_names_a_tab_id_reddens(tmp_path):
    """The bypass law. Plant the literal the way a hand-written frame would."""
    repo = _repo_copy(tmp_path)
    core = _core_copy(tmp_path)
    frame = core / "ui/panel/panel-frame.ts"
    frame.write_text("const OPENER_TAB = 'site';\n" + frame.read_text(encoding="utf-8"),
                     encoding="utf-8")
    r = run("--repo", str(repo), "--ui-root", str(core / "ui"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "'site'" in r.stdout and "panel-frame.ts" in r.stdout


def test_a_declared_tab_with_no_claim_reddens_and_skip_is_not_a_fix(tmp_path):
    repo = _repo_copy(tmp_path)
    core = _core_copy(tmp_path)
    allow = repo / "docs/contracts/coverage-allowlist.yaml"
    text = allow.read_text(encoding="utf-8")
    # The forbidden fix, verbatim: drop the `sources:` block and add a skip.
    start = text.index("    sources:\n      - panel/site-tab.ts\n")
    text = text[:start] + "    skip: [panel/site-tab.ts]\n" + text[start + len("    sources:\n      - panel/site-tab.ts\n"):]
    allow.write_text(text, encoding="utf-8")
    r = run("--repo", str(repo), "--ui-root", str(core / "ui"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tab 'site'" in r.stdout and "claims no `sources:` file" in r.stdout


def test_a_declared_tab_missing_from_the_allowlist_reddens(tmp_path):
    repo = _repo_copy(tmp_path)
    core = _core_copy(tmp_path)
    inv = core / "ui/panel/tabs.json"
    doc = json.loads(inv.read_text(encoding="utf-8"))
    doc["tabs"].append({"id": "telemetry", "title_msgid": "panel.tab.site",
                        "order": 900, "requires_identity_scope": False})
    inv.write_text(json.dumps(doc), encoding="utf-8")
    r = run("--repo", str(repo), "--ui-root", str(core / "ui"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tab 'telemetry'" in r.stdout


def test_the_vector_file_is_executed_not_decorative(tmp_path):
    """Corrupt an ACCEPT payload: the lane must redden naming the vector.

    Without this, `vectors/panel-tab-registration-v1.json` could become a file
    that documents rules nobody runs — the failure mode the C-0.1c law names.
    """
    repo = _repo_copy(tmp_path)
    core = _core_copy(tmp_path)
    vec = repo / "docs/contracts/vectors/panel-tab-registration-v1.json"
    doc = json.loads(vec.read_text(encoding="utf-8"))
    doc["accept"][0]["payload"]["page_html"] = "<div>content</div>"
    vec.write_text(json.dumps(doc), encoding="utf-8")
    r = run("--repo", str(repo), "--ui-root", str(core / "ui"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "vector accept/" in r.stdout
