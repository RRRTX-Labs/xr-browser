"""P14-CLOSE C-3 (P14-T7): the xr://identities dev page — host half.

The compiled identity_host's `manager-page` / `reset-all` subcommands are the
page's data source and its only purge-all escape. Locked here:

1. DEV-ONLY BY ENFORCEMENT: without --build-channel (default release) and
   under release / nightly-test, both subcommands refuse with the typed
   `build-channel-not-dev:<channel>` reason, exit 0, and emit NO page bytes
   (no rows, no domains). An unknown channel value is a usage error (exit 2).
2. The option never perturbs the frozen surface: the parity corpus replays
   byte-identically with `--build-channel dev` prepended.
3. Under dev: per-identity stats (tab count from the binding, storage bytes,
   permission count — null when absent, never a guessed 0), edits that touch
   display metadata only with typed refusals, the purge-unverified state from
   the host's named plant hook, and reset-all purging-and-verifying every
   identity (one planted residual => all_verified:false).
4. `manager-page-states` serves the core's kManagerPageStates (the list
   shield_state_check holds the view to).

C++-dependent tests SKIP VISIBLY when g++/make are absent (skip-policy law).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
XR_CORE = REPO.parent / "xr-core"
CORPUS = TOOLS / "parity" / "corpus-identity.json"
BUILD_DIR = REPO / "work" / "scratch" / "pytest-identity-build"
HAVE_CPP = shutil.which("g++") is not None and shutil.which("make") is not None
IDS = [{"entropy": "page-a", "display_name": "Work"},
       {"entropy": "page-b", "display_name": "Bank", "in_memory": True}]


@pytest.fixture(scope="module")
def host() -> Path:
    if not HAVE_CPP:
        pytest.skip("g++/make absent — C++ identity host skipped (skip-policy)")
    r = subprocess.run(["make", "-C", str(XR_CORE / "identity" / "tests"), "build",
                        f"BUILD={BUILD_DIR}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"make failed for identity:\n{r.stderr[-400:]}")
    return BUILD_DIR / "identity_host"


def run(host: Path, *argv: str) -> tuple[int, str, str]:
    p = subprocess.run([str(host), *argv], capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def page(host: Path, args: dict, channel: str = "dev") -> dict:
    rc, out, _ = run(host, "--build-channel", channel, "manager-page", json.dumps(args))
    assert rc == 0, out
    return json.loads(out)


def test_states_served_from_the_core(host: Path) -> None:
    rc, out, _ = run(host, "manager-page-states", "{}")
    assert rc == 0
    assert json.loads(out) == {"states": ["normal", "empty", "purge-unverified",
                                          "dev-refused"]}


@pytest.mark.parametrize("cmd", ["manager-page", "reset-all"])
@pytest.mark.parametrize("channel", [None, "release", "nightly-test"])
def test_non_dev_refuses_with_no_page_bytes(host: Path, cmd: str, channel: str | None) -> None:
    argv = ([] if channel is None else ["--build-channel", channel]) + \
        [cmd, json.dumps({"identities": IDS, "purge": [0]})]
    rc, out, _ = run(host, *argv)
    assert rc == 0
    assert json.loads(out) == {"error": "kRejected",
                               "reason": f"build-channel-not-dev:{channel or 'release'}"}
    assert "xr:" not in out and "rows" not in out  # nothing about any identity leaks


@pytest.mark.parametrize("bad", ["Dev", "beta", "", "dev "])
def test_unknown_channel_is_a_usage_error(host: Path, bad: str) -> None:
    rc, out, err = run(host, "--build-channel", bad, "manager-page", "{}")
    assert rc == 2 and out == "" and "--build-channel" in err


def test_frozen_surface_unperturbed_by_the_option(host: Path) -> None:
    cases = json.loads(CORPUS.read_text("utf-8"))["cases"]
    assert cases
    for case in cases[:12]:
        req = json.dumps({"method": case["method"], "args": case["args"]},
                         sort_keys=True, separators=(",", ":"))
        plain = subprocess.run([str(host)], input=req, capture_output=True, text=True)
        dev = subprocess.run([str(host), "--build-channel", "dev"], input=req,
                             capture_output=True, text=True)
        assert (plain.returncode, plain.stdout) == (dev.returncode, dev.stdout), case


def test_dev_page_stats_and_states(host: Path) -> None:
    assert page(host, {"identities": []})["state"] == "empty"
    p = page(host, {"identities": IDS, "permission_counts": [5],
                    "tabs": [{"identity": 0, "tab_id": 1}, {"identity": 0, "tab_id": 2},
                             {"identity": 1, "tab_id": 3}]})
    assert p["state"] == "normal" and p["purges"] == [] and p["edits"] == []
    a, b = p["rows"]
    assert (a["display_name"], a["tab_count"], a["permission_count"]) == ("Work", 2, 5)
    assert (b["tab_count"], b["permission_count"], b["in_memory"]) == (1, None, True)
    assert a["storage_bytes"] > 0 and a["lifecycle"] == "kActive"
    assert set(a) == {"domain", "display_name", "color", "glyph", "template_id", "in_memory",
                      "lifecycle", "tab_count", "storage_bytes", "permission_count"}


def test_dev_page_edits_and_typed_refusals(host: Path) -> None:
    p = page(host, {"identities": IDS, "edits": [
        {"identity": 0, "op": "rename", "value": "Client"},
        {"identity": 0, "op": "recolor", "value": "#0f9d58"},
        {"identity": 1, "op": "archive"},
        {"identity": 1, "op": "rename", "value": ""},
        {"identity": 1, "op": "recolor", "value": "red"}]})
    assert [e["ok"] for e in p["edits"]] == [True, True, True, False, False]
    assert p["edits"][3]["error"] == "kMalformedInput (name-empty)"
    assert p["edits"][4]["error"] == "kMalformedInput (color-not-hex)"
    a, b = p["rows"]
    assert (a["display_name"], a["color"], b["lifecycle"]) == ("Client", "#0f9d58", "kHibernated")
    rc, out, _ = run(host, "--build-channel", "dev", "manager-page",
                     json.dumps({"identities": IDS, "edits": [{"identity": 0, "op": "delete"}]}))
    assert rc == 1 and json.loads(out)["error"] == "kMalformedInput"


def test_purge_unverified_is_never_hidden(host: Path) -> None:
    p = page(host, {"identities": IDS, "purge": [0]})
    assert p["state"] == "normal" and p["purges"][0]["verified"] is True
    assert [r["display_name"] for r in p["rows"]] == ["Bank"]
    p = page(host, {"identities": IDS, "plant_residual": [1], "purge": [1]})
    assert p["state"] == "purge-unverified"
    assert p["purges"][0] == {"domain": p["purges"][0]["domain"], "verified": False,
                              "residual_kinds": ["stray-cache"]}


def test_reset_all_purges_and_verifies_everything(host: Path) -> None:
    rc, out, _ = run(host, "--build-channel", "dev", "reset-all", json.dumps({"identities": IDS}))
    r = json.loads(out)
    assert rc == 0 and r["destroyed"] == 2 and r["all_verified"] is True
    rc, out, _ = run(host, "--build-channel", "dev", "reset-all",
                     json.dumps({"identities": IDS, "plant_residual": [0]}))
    r = json.loads(out)
    assert r["all_verified"] is False
    assert [x["zero_residual_verified"] for x in r["results"]] == [False, True]
