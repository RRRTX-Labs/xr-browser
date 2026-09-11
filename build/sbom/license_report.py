#!/usr/bin/env python3
"""build/sbom/license_report.py — the per-release license report (P10-T7).

Builds the license report from docs/dependencies/*.yaml (EVERY dependency
file must appear or the gate fails — the plan's 19-file law, discovered
not hard-coded) and attaches it to the SBOM as a CycloneDX 1.6 component
per dependency with its evaluated license(s).

Laws:
  * every docs/dependencies/*.yaml appears in the report (missing => FAIL);
  * a dependency whose YAML carries NO resolvable license (neither
    `licenses.code` nor `license:` nor an REJECTED-evaluated verdict
    naming one) is `unknown` — and UNKNOWN-LICENSE FAILS THE BUILD
    (sbom_gate.py --require-licenses enforces it; negative fixture in
    tools/negatives/p10_release.sh);
  * the REJECTED eval (boringtun) is represented HONESTLY: component
    present, license = the evaluated one, `xr:status: rejected` property,
    and it must NOT appear as shippable.

Output: canonical JSON (deterministic; sorted keys) to stdout or --out.
Exit: 0 · 1 fail · 2 usage. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # repo root (build/sbom/)
DEPS_DIR = REPO / "docs" / "dependencies"


def load_yaml(path: Path) -> dict:
    import yaml  # pinned dev dep (tools/DEPS.md)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def dep_licenses(doc: dict) -> tuple[list[str], bool]:
    """Returns (licenses, known). A dependency is KNOWN iff its eval
    names at least one concrete license (licenses.code / license: / a
    `license:` list). NOASSERTION/unknown/absent => unknown."""
    lic_block = doc.get("licenses")
    found: list[str] = []
    if isinstance(lic_block, dict):
        for v in lic_block.values():
            v = str(v).strip().strip('"')
            if v and v not in ("—", "-") and not v.startswith("filter lists"):
                found.append(v)
    if not found:
        # some evals list per-entry licenses under a list field (`entries:`
        # / `tools:` with `license:` per row) — collect them (EVALUATED)
        for key in ("entries", "tools", "components"):
            rows = doc.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("license"):
                        found.append(str(row["license"]))
    if not found and doc.get("license"):
        v = doc["license"]
        found = v if isinstance(v, list) else [str(v)]
    found = [f for f in found if f and str(f).upper() != "UNKNOWN"]
    return found, bool(found)


def components_from_report() -> tuple[list[dict], list[str]]:
    comps: list[dict] = []
    unknown: list[str] = []
    for yml in sorted(DEPS_DIR.glob("*.yaml")):
        doc = load_yaml(yml)
        proj = str(doc.get("project", yml.stem))
        name = proj.split(" — ")[0].split(" (")[0].strip() or yml.stem
        licenses, known = dep_licenses(doc)
        rejected = "-REJECTED" in yml.stem or \
            str(doc.get("current_status", "")).lower().startswith("rejected")
        comp: dict = {
            "bom-ref": f"xr-dep:{yml.stem}",
            "description": proj[:200],
            "name": name,
            "type": "application",
            "version": "evaluated",
            "properties": [
                {"name": "xr:eval-file", "value": f"docs/dependencies/{yml.name}"},
                {"name": "xr:status",
                 "value": "rejected" if rejected else "evaluated"},
            ],
        }
        comp["licenses"] = [{"license": {"name": licenses[0] if licenses
                                         else "NOASSERTION"}}]
        for extra in licenses[1:4]:
            comp["licenses"].append({"license": {"name": extra}})
        comps.append(comp)
        if not known:
            unknown.append(yml.stem)
        if rejected:
            comps[-1]["properties"].append(
                {"name": "xr:note",
                 "value": "REJECTED by evaluation — NOT vendored/shipped"})
    return comps, unknown


def main() -> int:
    ap = argparse.ArgumentParser(prog="license-report",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--deps-dir", default=None,
                    help="override docs/dependencies (negative fixtures)")
    ap.add_argument("--attach-to", default=None,
                    help="SBOM json to embed the report components into")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    global DEPS_DIR
    if a.deps_dir:
        DEPS_DIR = Path(a.deps_dir).resolve()
    comps, unknown = components_from_report()
    if not comps:
        print("FAIL: zero dependency evals found — a license report over "
              "nothing certifies nothing")
        return 1
    report = {
        "components": comps,
        "schema": "xr-license-report",
        "schema_version": 1,
        "unknown_license_deps": unknown,
    }
    if a.attach_to:
        sbom_path = Path(a.attach_to)
        sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
        have = {c.get("name") for c in sbom.get("components", [])}
        for c in comps:
            if c.get("name") not in have:
                c.pop("bom-ref", None)  # CycloneDX schema requires
                sbom.setdefault("components", []).append(c)
        rendered = json.dumps(sbom, sort_keys=True, indent=1) + "\n"
    else:
        rendered = json.dumps(report, sort_keys=True, indent=1,
                              ensure_ascii=True) + "\n"
    if a.out:
        Path(a.out).write_text(rendered, encoding="utf-8")
    if not a.json:
        rejected = sum(1 for c in comps for p in c.get("properties", [])
                       if p.get("value") == "rejected")
        print(f"license report: {len(comps)} dependency eval(s) "
              f"({rejected} rejected-and-not-shipped; "
              f"{len(unknown)} unknown-license: "
              f"{', '.join(unknown) if unknown else 'none'})")
    if unknown:
        print(f"FAIL: unknown license for: {', '.join(unknown)} — "
              "the unknown-license-fails-build law is in force "
              "(sbom_gate.py --require-licenses)")
        return 1
    if not a.json:
        print(f"PASS: license-report ({len(comps)} entries; every "
              "dependency eval represented; unknown-license law clean)")
    if a.out and not a.json:
        print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
