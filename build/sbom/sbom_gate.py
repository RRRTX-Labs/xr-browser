"""build/sbom/sbom_gate.py — validate an SBOM against the vendored schema (stdlib).

jsonschema-free: JSON wellformedness + the vendored CycloneDX 1.6 schema's
own `required` arrays + component field asserts. Full JSON-Schema resolution
is NOT needed for the gate (and jsonschema is permitted-but-unpinned in P1;
we stay stdlib). Reference schema: build/sbom/cyclonedx-schema-1.6.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, repo_root  # noqa: E402

SCHEMA = "build/sbom/cyclonedx-schema-1.6.json"


def validate(sbom: dict, schema: dict) -> list[str]:
    fails: list[str] = []
    for req in schema.get("required", []):
        if req not in sbom:
            fails.append(f"missing required field {req!r}")
    if sbom.get("bomFormat") != "CycloneDX":
        fails.append("bomFormat must be 'CycloneDX'")
    if sbom.get("specVersion") != "1.6":
        fails.append("specVersion must be '1.6'")
    if "serialNumber" not in sbom:
        fails.append("serialNumber required")
    comps = sbom.get("components")
    if not isinstance(comps, list):
        fails.append("components must be a list")
    else:
        comp_req = set()
        comp_def = schema.get("definitions", {}).get("component", {})
        comp_req = set(comp_def.get("required", []))
        for i, c in enumerate(comps):
            if not isinstance(c, dict):
                fails.append(f"components[{i}] not an object")
                continue
            for req in comp_req:
                if req not in c:
                    fails.append(f"components[{i}].{req} missing")
    return fails


def main() -> None:
    parser = argparse.ArgumentParser(prog="build/sbom/sbom_gate.py",
                                     description="Validate an SBOM against the vendored CycloneDX 1.6 schema.")
    parser.add_argument("--sbom", required=True, help="sbom.json to validate")
    parser.add_argument("--schema", default=SCHEMA, help="schema path (repo-relative)")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        root = repo_root()
        schema = json.loads((root / args.schema).read_text(encoding="utf-8"))
        try:
            sbom = json.loads(Path(args.sbom).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError(f"{args.sbom}: not valid JSON: {exc}")
        fails = validate(sbom, schema)
        return emit(args.json, {"tool": "sbom_gate", "sbom": args.sbom,
                                "components": len(sbom.get("components", []))}, failures=fails)

    main_with_guard(run)


if __name__ == "__main__":
    main()
