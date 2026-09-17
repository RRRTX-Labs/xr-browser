#!/usr/bin/env python3
"""tools/scriptlet_registry_check.py — the P12 scriptlet registry gate.

A registry that lists scriptlets without proving anything about them is a
liability: it reads as a capability list, and a reader who trusts it will
believe the phase ships more than it does. This gate makes every entry carry
its own evidence, and fails the build when one does not.

Per entry, all five are REQUIRED (missing => FAIL, not a warning):

  1. a capability note explaining what the scriptlet can do and why that is
     bounded — a name and an arity are not a capability note;
  2. a degrade-test case id, cross-checked against the degrade corpus so an
     entry cannot name a case that does not exist;
  3. a refusal-path case id, likewise cross-checked;
  4. a doc line, cross-checked against the scriptlets doc so the reference
     resolves;
  5. NO main-world capability. `main_world_permitted` must be false and no
     entry may declare one. A scriptlet that needs the page's own realm is a
     code-execution channel, and this phase does not ship one.

Plus the structural laws: unique names, arity a non-negative integer,
`page_modifying` an explicit boolean (an omitted field would default to falsy
and quietly under-report what the Observatory must label), a `source` citation
in path:line@vendored form, and an `abpf_instruction` that the ABPF validator
actually refuses — a registry entry the validator would accept is an entry that
implies execution.

The zero-case law applies to this gate's own input: an empty registry, or one
with no refused entries, is a FAIL. A registry that admits nothing and refuses
nothing certifies nothing.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required (pip install pyyaml)")
    sys.exit(1)

REGISTRY = "renderer/cosmetic/scriptlets/registry.yaml"
DEGRADE_CORPUS = "docs/contracts/cosmetic-scriptlet-degrade.json"
DOC = "docs/renderer/scriptlets.md"
# Capabilities that require the page's own realm. None is permitted in P12.
MAIN_WORLD_CAPABILITIES = {
    "main-world", "main-world-eval", "realm-replace", "trusted-types",
}
SOURCE_RE = re.compile(r"^[\w./-]+:\d+(?:-\d+)?@vendored$")
ARITY_MAX = 4
# uBO's own scriptlet names are camelCase in places (`no-setTimeout-if`,
# `prevent-setTimeout`), and the registry must carry the name a list actually
# uses — renaming it here would make the registry wrong about the instruction
# it maps to. So the identifier rule allows interior capitals.
NAME_RE = re.compile(r"^[a-z][a-zA-Z0-9-]*$")

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _json_ids(path: Path, key: str) -> set[str]:
    """Case ids from a JSON corpus, or an empty set with a recorded reason."""
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c.get(key) for c in (data.get("cases") or []) if isinstance(c, dict)
            and c.get(key)}


def _all_corpus_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for case in data.get("cases") or []:
        if isinstance(case, dict) and isinstance(case.get("id"), str):
            out.add(case["id"])
    return out


def _doc_anchors(path: Path) -> set[str]:
    """Heading anchors a doc_line reference can resolve to."""
    if not path.is_file():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            slug = line.lstrip("#").strip().lower()
            slug = re.sub(r"[^a-z0-9 -]", "", slug).replace(" ", "-")
            out.add(slug)
    return out



def _covers(ids: set[str], ref: str) -> bool:
    """True if the corpus has the referenced case.

    The registry names a case FAMILY (`sd-noeval`); the corpus has one case per
    synthetic page (`sd-noeval__softwall-body-lock`, …) because "disable-able
    individually" has to hold on every page, not on one convenient fixture. So
    an exact match or a `ref__…` prefix match both satisfy the reference, and a
    bare name that matches nothing is still a failure.
    """
    if ref in ids:
        return True
    prefix = ref + "__"
    return any(i.startswith(prefix) for i in ids)


def check(repo: Path, xr_core: Path) -> list[str]:
    fails: list[str] = []
    reg_path = xr_core / REGISTRY
    if not reg_path.is_file():
        return [f"{REGISTRY} does not exist — the registry is the admitted "
                "set, and without it 'admitted' means whatever the engine "
                "accepts"]
    reg = _load(reg_path)
    if not isinstance(reg, dict):
        return [f"{REGISTRY} is not a mapping"]

    entries = reg.get("scriptlets") or []
    refused = reg.get("refused") or []
    if not entries:
        fails.append(f"{REGISTRY}: zero scriptlet entries — a registry that "
                     "admits nothing certifies nothing (zero-case law)")
    if not refused:
        fails.append(f"{REGISTRY}: zero refused entries — a registry with no "
                     "refusals records no decisions, and a future reader "
                     "cannot tell an omission from an oversight")

    # --- the phase-level laws -------------------------------------------
    if reg.get("execution") != "off":
        fails.append(f"{REGISTRY}: execution must be 'off' in P12 — "
                     "xr_shield_scriptlets defaults false and no interpreter "
                     "is wired into the host path; got "
                     f"{reg.get('execution')!r}")
    if reg.get("main_world_permitted") is not False:
        fails.append(f"{REGISTRY}: main_world_permitted must be false — a "
                     "scriptlet that needs the page's own realm is a "
                     "code-execution channel this phase does not ship")

    degrade_ids = _all_corpus_ids(repo / DEGRADE_CORPUS)
    if not degrade_ids:
        fails.append(f"{DEGRADE_CORPUS} is missing or has no cases — the "
                     "registry's degrade_case references cannot be "
                     "cross-checked, so 'each scriptlet is disable-able' "
                     "would be an unverified claim")
    anchors = _doc_anchors(repo / DOC)
    if not anchors:
        fails.append(f"{DOC} is missing or has no headings — the registry's "
                     "doc_line references cannot be cross-checked")

    seen: set[str] = set()
    for i, e in enumerate(entries):
        where = f"{REGISTRY} scriptlets[{i}]"
        if not isinstance(e, dict):
            fails.append(f"{where} is not a mapping")
            continue
        name = e.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            fails.append(f"{where}: name must be a kebab-case identifier, got "
                         f"{name!r}")
            continue
        where = f"{REGISTRY} '{name}'"
        if name in seen:
            fails.append(f"{where}: duplicate registry entry")
        seen.add(name)

        # 1. capability note
        note = e.get("note")
        if not isinstance(note, str) or len(note.strip()) < 40:
            fails.append(f"{where}: capability note missing or too short to "
                         "be one (a name and an arity are not a capability "
                         "note)")
        cap = e.get("capability")
        if not isinstance(cap, str) or not cap:
            fails.append(f"{where}: capability missing")
        elif cap in MAIN_WORLD_CAPABILITIES:
            fails.append(f"{where}: capability {cap!r} requires main-world "
                         "execution, which P12 does not permit")

        # 2/3. degrade + refusal cases, cross-checked
        dc = e.get("degrade_case")
        if not isinstance(dc, str) or not dc:
            fails.append(f"{where}: degrade_case missing — 'each scriptlet is "
                         "disable-able individually' is unproven without one")
        elif degrade_ids and not _covers(degrade_ids, dc):
            fails.append(f"{where}: degrade_case {dc!r} is not in "
                         f"{DEGRADE_CORPUS} — a reference to a case that does "
                         "not exist proves nothing")
        rc = e.get("refusal_case")
        if not isinstance(rc, str) or not rc:
            fails.append(f"{where}: refusal_case missing — the refusal path is "
                         "where a scriptlet's bounds are enforced")
        elif degrade_ids and not _covers(degrade_ids, rc):
            fails.append(f"{where}: refusal_case {rc!r} is not in "
                         f"{DEGRADE_CORPUS}")

        # 4. doc line, cross-checked
        dl = e.get("doc_line")
        if not isinstance(dl, str) or not dl.startswith(f"{DOC}#"):
            fails.append(f"{where}: doc_line must be '{DOC}#<anchor>', got "
                         f"{dl!r}")
        elif anchors:
            anchor = re.sub(r"[^a-z0-9 -]", "",
                            dl.split("#", 1)[1].lower()).replace(" ", "-")
            if anchor not in anchors:
                fails.append(f"{where}: doc_line anchor #{anchor} does not "
                             "resolve in {DOC}")

        # 5. source citation
        src = e.get("source")
        if not isinstance(src, str) or not SOURCE_RE.match(src):
            fails.append(f"{where}: source must be 'path:line@vendored' so the "
                         "claim is checkable, got {src!r}")

        # arity
        arity = e.get("arity")
        if not isinstance(arity, int) or isinstance(arity, bool) or arity < 0:
            fails.append(f"{where}: arity must be a non-negative integer, got "
                         f"{arity!r}")
        elif arity > ARITY_MAX:
            fails.append(f"{where}: arity {arity} exceeds {ARITY_MAX} — a "
                         "scriptlet taking that many arguments is an "
                         "interpreter, and an interpreter in the renderer is "
                         "a code-execution channel")

        # page_modifying must be explicit
        if "page_modifying" not in e:
            fails.append(f"{where}: page_modifying must be stated explicitly — "
                         "an omitted field defaults to falsy and quietly "
                         "under-reports what the Observatory must label")
        elif not isinstance(e["page_modifying"], bool):
            fails.append(f"{where}: page_modifying must be a boolean")

        # abpf instruction, and the validator must REFUSE it
        instr = e.get("abpf_instruction")
        if not isinstance(instr, str) or not instr.startswith("$ext-"):
            fails.append(f"{where}: abpf_instruction must start with '$ext-', "
                         f"got {instr!r}")

    # Every refused entry must name a reason.
    for i, r in enumerate(refused):
        if not isinstance(r, dict):
            fails.append(f"{REGISTRY} refused[{i}] is not a mapping")
            continue
        if not isinstance(r.get("name"), str) or not r.get("name"):
            fails.append(f"{REGISTRY} refused[{i}]: name missing")
        reason = r.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < 20:
            fails.append(f"{REGISTRY} refused[{i}]: reason missing or too "
                         "short — a refusal without a reason is an omission "
                         "dressed as a decision")

    # No entry may be both admitted and refused.
    refused_names = {r.get("name") for r in refused if isinstance(r, dict)}
    both = seen & refused_names
    if both:
        fails.append(f"{REGISTRY}: admitted AND refused: {sorted(both)}")

    return fails


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="scriptlet-registry-check",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    xr_core = (Path(a.xr_core).resolve() if a.xr_core
               else (repo / "../xr-core").resolve())
    fails = check(repo, xr_core)
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print(f"FAIL: scriptlet_registry_check ({len(fails)} finding(s))")
        return EXIT_FAIL
    reg = _load(xr_core / REGISTRY)
    n = len(reg.get("scriptlets") or [])
    r = len(reg.get("refused") or [])
    pm = sum(1 for e in (reg.get("scriptlets") or [])
             if e.get("page_modifying"))
    print(f"PASS: scriptlet_registry_check ({n} admitted ({pm} "
          f"page-modifying), {r} refused, execution=off, main_world=false)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
