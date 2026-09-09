"""P8-T7 help-deep-link tooling tests: schema <-> registry mapping and the
contract-doc marker gate.

Stdlib + pytest; positive test pins the live repo state (3 sections, 3
settings commands, all enabled) so drift fails loudly.
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

COMMANDS_TABLE = textwrap.dedent("""\
    # Command registry (v1)

    | id | scope | tier | danger | predicate | status |
    | --- | --- | --- | --- | --- | --- |
    | `settings.network` | global | tier2 | safe | `always` | enabled |
    | `settings.privacy` | global | tier2 | safe | `always` | enabled |
    | `settings.identity` | global | tier2 | safe | `always` | enabled |
    | `tor.open` | global | tier1 | caution | `tor.engine-ready` | disabled (placeholder) |
""")


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / "help_deep_link.py"),
                           *args], cwd=cwd or REPO, capture_output=True,
                          text=True)


def _schema(tmp: Path, sections: list[dict], anchor_root: str = "xr://settings"
            ) -> Path:
    core = tmp / "xr-core"
    (core / "settings/core").mkdir(parents=True)
    p = core / "settings/core/settings_schema_v1.json"
    p.write_text(json.dumps({"schema": "xr-settings-schema", "anchor_root":
                             anchor_root, "sections": sections, "settings": []}))
    return p


def _contract(tmp: Path) -> Path:
    c = tmp / "contract.md"
    c.write_text("Anchors: xr://help/<id> and xr://settings/<section>; "
                 "fallback listed.\n")
    return c


def test_live_repo_passes() -> None:
    r = run()
    assert r.returncode == 0, r.stderr
    assert "3 sections" in r.stdout


def test_missing_section_command_fails(tmp_path: Path) -> None:
    schema = _schema(tmp_path, [{"id": "network", "settings": []},
                                {"id": "missing-sec", "settings": []}])
    cmds = tmp_path / "commands.md"
    cmds.write_text(COMMANDS_TABLE)
    r = run("--xr-core", str(schema.parent.parent.parent),
            "--commands", str(cmds), "--contract", str(_contract(tmp_path)))
    assert r.returncode == 1
    assert "settings.missing-sec" in r.stderr


def test_disabled_settings_command_fails(tmp_path: Path) -> None:
    schema = _schema(tmp_path, [{"id": "network", "settings": []}])
    cmds = tmp_path / "commands.md"
    cmds.write_text("| `settings.network` | global | tier2 | safe | "
                    "`always` | disabled (x) |\n")
    r = run("--xr-core", str(schema.parent.parent.parent),
            "--commands", str(cmds), "--contract", str(_contract(tmp_path)))
    assert r.returncode == 1
    assert "disabled" in r.stderr


def test_orphan_settings_command_fails(tmp_path: Path) -> None:
    schema = _schema(tmp_path, [{"id": "network", "settings": []}])
    cmds = tmp_path / "commands.md"
    cmds.write_text("| `settings.ghost` | global | tier2 | safe | "
                    "`always` | enabled |\n")
    r = run("--xr-core", str(schema.parent.parent.parent),
            "--commands", str(cmds), "--contract", str(_contract(tmp_path)))
    assert r.returncode == 1
    assert "no schema section 'ghost'" in r.stderr


def test_anchor_root_drift_fails(tmp_path: Path) -> None:
    _schema(tmp_path, [{"id": "network", "settings": []}],
            anchor_root="xr://wrong")
    cmds = tmp_path / "commands.md"
    cmds.write_text(COMMANDS_TABLE)
    r = run("--xr-core", str(tmp_path / "xr-core"),
            "--commands", str(cmds), "--contract", str(_contract(tmp_path)))
    assert r.returncode == 1
    assert "anchor_root" in r.stderr


def test_contract_doc_marker_gate(tmp_path: Path) -> None:
    _schema(tmp_path, [{"id": "network", "settings": []}])
    cmds = tmp_path / "commands.md"
    cmds.write_text(COMMANDS_TABLE)
    c = tmp_path / "contract.md"
    c.write_text("schemes not cited here anymore.\n")
    r = run("--xr-core", str(tmp_path / "xr-core"),
            "--commands", str(cmds), "--contract", str(c))
    assert r.returncode == 1
    assert "no longer cites" in r.stderr
