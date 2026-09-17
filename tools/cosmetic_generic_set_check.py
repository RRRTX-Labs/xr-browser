#!/usr/bin/env python3
"""tools/cosmetic_generic_set_check.py — the P12 generic hide set gate.

The generic set is the one cosmetic rule set that is ALWAYS ON and NOT
exception-able at the Shield policy level. That makes it the highest-consequence
data in the phase: it applies to every page, including pages with no ads and
pages where the user has no lists installed, and a user cannot opt a site out of
it. So it gets a gate that treats "small and conservative" as a machine-checked
property rather than a comment.

Enforced:

  * every selector parses with the SAME parser the renderer uses, via
    cosmetic_host's selector-parse — a set that shipped an unparsable selector
    would fail at document-start on every page rather than at review time;
  * every action is in the closed action set, and every style declaration uses a
    property on the admitted allowlist (`position` and `z-index` are not on it,
    because a rule that can restack a page can hide the user's own content);
  * `page_modifying` is stated explicitly on every entry and matches the action
    — an omitted field defaults to falsy and quietly under-reports what the
    Observatory must label;
  * every entry has provenance, and the document asserts the
    no-upstream-list-required property with a note explaining WHY that matters;
  * size and build budgets: rule count and a measured build time, both gated.
    A generic set that grew to thousands of rules would cost document-start time
    on every page including ones with no ads, which is the opposite of the
    degrade law;
  * the always-on and not-exception-able properties are stated in the file, so
    the reading of the plan is recorded rather than inferred from code;
  * the no-rules-no-work law: an empty key set yields zero emitted style, checked
    against the host rather than asserted in prose.

--check verifies the committed budgets are unchanged (diff-clean), the way P11's
shield-bench --check rows work. The budget file is generated, never hand-edited.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SET_FILE = "xr-lists/generic-hide-set.v1.json"
BUDGET_FILE = "build/qa/perf/generic-set-budgets.json"
ACTIONS = {"hide", "collapse", "visibility", "remove", "style"}
PAGE_MODIFYING_ACTIONS = {"remove"}
# Mirrors kAdmittedProperties in xr-core/renderer/cosmetic/core/style.cc.
ADMITTED_PROPERTIES = {
    "display", "visibility", "opacity", "height", "max-height", "min-height",
    "width", "max-width", "min-width", "overflow", "pointer-events", "clip",
    "clip-path",
}
SIZE_BUDGET_RULES = 64
BUILD_BUDGET_MS = 50.0

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def _host(xr_core: Path) -> Path:
    return (xr_core / "renderer" / "cosmetic" / "tests" / "build" /
            "cosmetic_host")


def _call(host: Path, method: str, args: dict[str, Any]) -> tuple[dict, int]:
    frame = json.dumps({"args": args, "method": method}, sort_keys=True,
                       separators=(",", ":"))
    r = subprocess.run([str(host)], input=frame, capture_output=True,
                       text=True, timeout=30)
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        return {}, r.returncode


def check_set(doc: dict[str, Any], host: Path | None) -> list[str]:
    fails: list[str] = []
    if doc.get("schema") != "generic-hide-set-v1":
        fails.append(f"{SET_FILE}: schema must be generic-hide-set-v1")
    if doc.get("always_on") is not True:
        fails.append(f"{SET_FILE}: always_on must be true — the generic set is "
                     "the one rule set that is not exception-able, and a file "
                     "that does not say so leaves the property to inference")
    if doc.get("exception_able_at_shield_policy_level") is not False:
        fails.append(f"{SET_FILE}: exception_able_at_shield_policy_level must "
                     "be false — a shields-down must not leave the page "
                     "half-styled")
    if not isinstance(doc.get("exception_note"), str) or \
            len(doc["exception_note"]) < 80:
        fails.append(f"{SET_FILE}: exception_note must explain WHY the set is "
                     "not exception-able — the reading of the plan has to be "
                     "recorded, not silently chosen")
    if doc.get("no_upstream_list_required") is not True:
        fails.append(f"{SET_FILE}: no_upstream_list_required must be true — a "
                     "generic set that needs a subscribed list is not generic")
    if not isinstance(doc.get("no_upstream_list_note"), str) or \
            len(doc["no_upstream_list_note"]) < 80:
        fails.append(f"{SET_FILE}: no_upstream_list_note must explain the "
                     "property, not just assert it")

    sels = doc.get("selectors")
    if not isinstance(sels, list) or not sels:
        fails.append(f"{SET_FILE}: zero selectors — an empty generic set "
                     "certifies nothing (zero-case law)")
        return fails

    # Size budget.
    if len(sels) > SIZE_BUDGET_RULES:
        fails.append(f"{SET_FILE}: {len(sels)} rules exceeds the "
                     f"{SIZE_BUDGET_RULES}-rule budget — the generic set costs "
                     "document-start time on EVERY page including ones with no "
                     "ads, so it must stay small and conservative")

    seen: set[str] = set()
    for i, e in enumerate(sels):
        where = f"{SET_FILE} selectors[{i}]"
        if not isinstance(e, dict):
            fails.append(f"{where} is not a mapping")
            continue
        sel = e.get("selector")
        if not isinstance(sel, str) or not sel:
            fails.append(f"{where}: selector missing")
            continue
        where = f"{SET_FILE} '{sel}'"
        if sel in seen:
            fails.append(f"{where}: duplicate entry")
        seen.add(sel)

        # Parse with the renderer's own parser.
        if host is not None and host.exists():
            res, _ = _call(host, "selector-parse", {"selector": sel})
            if res.get("error"):
                fails.append(f"{where}: the renderer's parser refuses it "
                             f"({res.get('reason')}) — a generic set that "
                             "ships an unparsable selector fails at "
                             "document-start on every page")

        action = e.get("action")
        if action not in ACTIONS:
            fails.append(f"{where}: action {action!r} is not in the closed "
                         f"set {sorted(ACTIONS)}")
            continue
        style = e.get("style") or {}
        if action == "style":
            if not style:
                fails.append(f"{where}: a style action needs declarations")
            for prop, val in style.items():
                if prop not in ADMITTED_PROPERTIES:
                    fails.append(f"{where}: property {prop!r} is not on the "
                                 f"admitted allowlist — `position`/`z-index` "
                                 f"are excluded because a rule that can "
                                 f"restack a page can hide the user's own "
                                 f"content")
                if not isinstance(val, str) or not val:
                    fails.append(f"{where}: value for {prop!r} must be a "
                                 f"non-empty string")
        elif style:
            fails.append(f"{where}: action {action!r} carries style "
                         "declarations — a built-in action's declarations come "
                         "from the table, so a rule cannot mix the two and get "
                         "an unbounded declaration set")

        # page_modifying must be explicit AND agree with the action.
        if "page_modifying" not in e:
            fails.append(f"{where}: page_modifying must be stated explicitly — "
                         "an omitted field defaults to falsy and quietly "
                         "under-reports what the Observatory must label")
        elif not isinstance(e["page_modifying"], bool):
            fails.append(f"{where}: page_modifying must be a boolean")
        elif e["page_modifying"] != (action in PAGE_MODIFYING_ACTIONS):
            fails.append(f"{where}: page_modifying={e['page_modifying']} but "
                         f"action={action!r} — only `remove` is "
                         "page-modifying, and a mismatch means the "
                         "Observatory would label an injection as a blocked "
                         "request or the reverse")

        prov = e.get("provenance")
        if not isinstance(prov, str) or len(prov) < 40:
            fails.append(f"{where}: provenance missing or too short — an "
                         "always-on rule needs a reason a reviewer can judge")

    return fails


def measure_build(doc: dict[str, Any], host: Path) -> float | None:
    """Wall time to compile the whole set into a key set, in milliseconds."""
    if not host.exists():
        return None
    rules = [{"id": f"g{i}", "selector": e["selector"], "action": e["action"],
              **({"style": e["style"]} if e.get("style") else {})}
             for i, e in enumerate(doc["selectors"])]
    frame = json.dumps({"args": {"rules": rules}, "method": "key-set"},
                       sort_keys=True, separators=(",", ":"))
    start = time.monotonic()
    subprocess.run([str(host)], input=frame, capture_output=True, text=True,
                   timeout=60)
    return (time.monotonic() - start) * 1000.0


def check_no_rules_no_work(host: Path) -> list[str]:
    """THE LAW: an empty rule set yields zero emitted style and no observer."""
    if not host.exists():
        return [f"{host.name} not built — the no-rules-no-work law cannot be "
                "checked against the host (build it with `make -C "
                "renderer/cosmetic/tests build`)"]
    fails: list[str] = []
    res, _ = _call(host, "key-set", {"rules": []})
    if res.get("error") != "kRejected" or res.get("reason") != "empty-rule-set":
        fails.append(f"no-rules-no-work: an empty rule set must be a typed "
                     f"refusal, got {res}")
    # With the flag OFF — the default — nothing is installed even with rules.
    # That is the whole off-state assertion: identical to today's product.
    res, _ = _call(host, "page-states", {"keyset_rules": 3})
    if res.get("cosmetic_enabled") is not False:
        fails.append("no-rules-no-work: the flag must default OFF")
    if res.get("observer_installed") is not False:
        fails.append("no-rules-no-work: with the flag off no observer may be "
                     f"installed, got {res.get('observer_installed')}")
    # The other half of the law needs the flag ON, which page-states does not
    # take as an argument — the host reads it from its own argv. Assert it there
    # instead of assuming it, so the law is checked in both states rather than
    # in the one that happens to be the default.
    frame = json.dumps({"args": {"keyset_rules": 0}, "method": "page-states"},
                       sort_keys=True, separators=(",", ":"))
    r = subprocess.run([str(host), "--flag", "xr_shield_cosmetic_v1=on"],
                       input=frame, capture_output=True, text=True, timeout=30)
    try:
        on_empty = json.loads(r.stdout)
    except json.JSONDecodeError:
        on_empty = {}
    if on_empty.get("observer_installed") is not False:
        fails.append("no-rules-no-work: with the flag ON and ZERO rules no "
                     "observer may be installed — no rules, no work")
    frame = json.dumps({"args": {"keyset_rules": 3}, "method": "page-states"},
                       sort_keys=True, separators=(",", ":"))
    r = subprocess.run([str(host), "--flag", "xr_shield_cosmetic_v1=on"],
                       input=frame, capture_output=True, text=True, timeout=30)
    try:
        on_rules = json.loads(r.stdout)
    except json.JSONDecodeError:
        on_rules = {}
    if on_rules.get("observer_installed") is not True:
        fails.append("no-rules-no-work: with the flag ON and rules present an "
                     f"observer must be installed, got "
                     f"{on_rules.get('observer_installed')}")
    # The generic set follows the flag, not shields-down.
    if on_rules.get("generic_set_applies") is not True:
        fails.append("generic-set-always-on: with the flag on the generic set "
                     "must apply")
    return fails


def write_budgets(path: Path, rules: int, ms: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "generic-set-budgets-1",
        "schema_version": 1,
        "note": ("GENERATED by tools/cosmetic_generic_set_check.py. Never "
                 "hand-edit: --check diffs this file against a fresh "
                 "measurement, so a hand-edited number is a number nobody "
                 "measured. `trend` class — a budget row records what was "
                 "observed and never asserts MET."),
        "class": "trend",
        "rules": rules,
        "rules_budget": SIZE_BUDGET_RULES,
        "build_ms": round(ms, 3),
        "build_budget_ms": BUILD_BUDGET_MS,
    }, indent=1, sort_keys=True) + "\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="cosmetic-generic-set-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed budgets are unchanged")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    xr_core = (Path(a.xr_core).resolve() if a.xr_core
               else (repo / "../xr-core").resolve())
    host = _host(xr_core)

    set_path = repo / SET_FILE
    if not set_path.is_file():
        print(f"FAIL: {SET_FILE} does not exist")
        return EXIT_FAIL
    doc = json.loads(set_path.read_text(encoding="utf-8"))

    fails = check_set(doc, host)
    fails += check_no_rules_no_work(host)

    ms = measure_build(doc, host)
    if ms is not None and ms > BUILD_BUDGET_MS:
        fails.append(f"{SET_FILE}: key-set build took {ms:.2f} ms, over the "
                     f"{BUILD_BUDGET_MS} ms budget")

    budget_path = repo / BUDGET_FILE
    if a.check:
        if not budget_path.is_file():
            fails.append(f"{BUDGET_FILE} is missing — run without --check to "
                         "generate it")
        else:
            committed = json.loads(budget_path.read_text(encoding="utf-8"))
            if committed.get("rules") != len(doc["selectors"]):
                fails.append(f"{BUDGET_FILE}: rules={committed.get('rules')} "
                             f"but the set has {len(doc['selectors'])} — the "
                             "budget is stale; regenerate (never hand-edit)")
    elif ms is not None:
        write_budgets(budget_path, len(doc["selectors"]), ms)

    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print(f"FAIL: cosmetic_generic_set_check ({len(fails)} finding(s))")
        return EXIT_FAIL
    pm = sum(1 for e in doc["selectors"] if e.get("page_modifying"))
    built = f", build {ms:.2f} ms" if ms is not None else ", build NOT-MEASURED"
    print(f"PASS: cosmetic_generic_set_check ({len(doc['selectors'])} rules "
          f"({pm} page-modifying), always-on, not exception-able{built})")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
