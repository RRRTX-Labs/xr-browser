#!/usr/bin/env python3
"""tools/xr_schema.py — strict schema validation + forward-only migration (T9).

Hand-rolled strict validator for XR's schema subset (no jsonschema dependency,
per DEPENDENCY RULES). Supports the strict keywords we actually use:
  type (object/array/string/integer/boolean), additionalProperties:false,
  required, properties, enum, const, const_false.

Also the versions-from-creation law (xr-schema-v1.md):
  * `stamp`   adds {version, created_at} to a fresh row (created_at fixed once).
  * `migrate` applies a forward-only chain; a downgrade (--to below current)
    is REJECTED with exit 1.

Stdlib only. Exit: 0 pass · 1 fail/downgrade · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

SCHEMA_DIR = "docs/contracts"
SCHEMAS = {
    "effective-policy": "effective-policy-v1.schema.json",
    "policy-change-event": "policy-change-event-v1.schema.json",
    "command-descriptor": "command-descriptor-v1.schema.json",
    "list-bundle": "list-bundle-manifest-v1.schema.json",
    "update-manifest": "update-manifest-31.schema.json",
}


def _validate(node: Any, schema: dict[str, Any], path: str, errs: list[str]) -> None:
    t = schema.get("type")
    if t == "object":
        if not isinstance(node, dict):
            errs.append(f"{path}: expected object")
            return
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in node:
                if k not in props:
                    errs.append(f"{path}.{k}: additional property not allowed")
        for req in schema.get("required", []):
            if req not in node:
                errs.append(f"{path}.{req}: required property missing")
        for k, sub in props.items():
            if k in node:
                _validate(node[k], sub, f"{path}.{k}", errs)
    elif t == "array":
        if not isinstance(node, list):
            errs.append(f"{path}: expected array")
    elif t == "string":
        if not isinstance(node, str):
            errs.append(f"{path}: expected string")
    elif t == "integer":
        if not isinstance(node, int) or isinstance(node, bool):
            errs.append(f"{path}: expected integer")
    elif t == "boolean":
        if not isinstance(node, bool):
            errs.append(f"{path}: expected boolean")
    if "enum" in schema and node not in schema["enum"]:
        errs.append(f"{path}: {node!r} not in enum {schema['enum']}")
    if "const" in schema and node != schema["const"]:
        errs.append(f"{path}: {node!r} != const {schema['const']!r}")
    if schema.get("const_false") and node is not False:
        errs.append(f"{path}: must be false (contract invariant)")


def cmd_validate(args) -> int:
    schema_path = Path(args.repo) / SCHEMA_DIR / SCHEMAS.get(args.contract, "")
    if not schema_path.exists():
        print(f"FAIL: unknown contract/schema: {args.contract}", file=sys.stderr)
        return EXIT_FAIL
    schema = json.loads(schema_path.read_text())
    doc = json.loads(Path(args.file).read_text())
    errs: list[str] = []
    _validate(doc, schema, "$", errs)
    if args.json:
        print(json.dumps({"tool": "xr_schema", "contract": args.contract,
                          "status": "pass" if not errs else "fail", "errors": errs}, indent=2))
    else:
        for e in errs:
            print(f"FAIL: {e}")
        print(f"{'PASS' if not errs else 'FAIL'}: xr_schema validate {args.contract}")
    return EXIT_PASS if not errs else EXIT_FAIL


def cmd_stamp(args) -> int:
    doc = json.loads(Path(args.file).read_text())
    if "version" not in doc:
        doc["version"] = 1
    if "created_at" not in doc:
        doc["created_at"] = int(args.created_at)  # fixed once; caller supplies.
    print(json.dumps(doc, sort_keys=True, indent=1))
    return EXIT_PASS


# Forward-only migration registry. Each fn: row@vN -> row@v(N+1).
def _v1_to_v2(row: dict[str, Any]) -> dict[str, Any]:
    r = dict(row)
    r["version"] = 2
    r.setdefault("migrated_note", "v1->v2 example: no field change")
    return r


MIGRATIONS = {1: _v1_to_v2}


def cmd_migrate(args) -> int:
    doc = json.loads(Path(args.file).read_text())
    cur = int(doc.get("version", 1))
    target = int(args.to)
    if target < cur:
        print(f"FAIL: downgrade rejected ({cur} -> {target})", file=sys.stderr)
        return EXIT_FAIL
    while cur < target:
        fn = MIGRATIONS.get(cur)
        if fn is None:
            print(f"FAIL: no migration from v{cur}", file=sys.stderr)
            return EXIT_FAIL
        doc = fn(doc)
        cur = int(doc["version"])
    print(json.dumps(doc, sort_keys=True, indent=1))
    return EXIT_PASS


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="xr_schema", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("contract"); v.add_argument("file")
    s = sub.add_parser("stamp"); s.add_argument("file"); s.add_argument("--created-at", dest="created_at", default="0")
    m = sub.add_parser("migrate"); m.add_argument("file"); m.add_argument("--to", required=True)
    args = p.parse_args(argv)
    return {"validate": cmd_validate, "stamp": cmd_stamp, "migrate": cmd_migrate}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
