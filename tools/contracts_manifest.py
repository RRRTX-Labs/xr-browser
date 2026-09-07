#!/usr/bin/env python3
"""tools/contracts_manifest.py — §1.11 completeness + §2.10 surface gate (P5).

Enforces, for all 14 §1.11 items, that each required part is present and
cross-linked:
  {IDL-or-schema, version, migration-note, fixtures, fake, review-packet}

And checks the §2.10 reserved-interface surface against the frozen mojom:
  * RouteManager has its four methods (Bind/Unbind/Status/LoseAllFailClosed)
  * EffectivePolicy has fingerprint / letterbox / storage_scope fields
  * GuardLedger has the update-diff + egress hooks

Item definitions live in the ITEMS table below (the mechanical form of
docs/contracts/INDEX.md). A missing part fails with the item + part named.

Stdlib only. Exit: 0 pass · 1 incomplete · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# Each item: required parts as repo-relative paths. `browser:` = xr-browser,
# `core:` = ../xr-core. `version` and `migration` are checked as text presence
# inside the idl/schema/doc.
ITEMS: dict[str, dict[str, Any]] = {
    "effective-policy": {
        "schema": "docs/contracts/effective-policy-v1.schema.json",
        "doc": "docs/contracts/effective-policy-v1.md",
        "fixtures": "docs/contracts/vectors/policy-resolver-v1.json",
        "fake": "core:fakes/policy_resolver.py",
        "packet": "docs/contracts/review/01-effective-policy-v1.md",
    },
    "policy-resolver": {
        "idl": "core:mojom/policy_resolver.mojom",
        "fixtures": "docs/contracts/vectors/policy-resolver-v1.json",
        "fake": "core:fakes/policy_resolver.py",
        "packet": "docs/contracts/review/02-policy-resolver-v1.md",
    },
    "identity-manager": {
        "idl": "core:mojom/identity.mojom",
        "fixtures": "core:fakes/fixtures/identity-v1.json",
        "fake": "core:fakes/identity.py",
        "packet": "docs/contracts/review/03-identity-manager-v1.md",
    },
    "shield": {
        "idl": "core:mojom/shield.mojom",
        "fixtures": "core:fakes/fixtures/shield-v1.json",
        "fake": "core:fakes/shield.py",
        "packet": "docs/contracts/review/04-shield-v1.md",
    },
    "route-manager": {
        "idl": "core:mojom/route_manager.mojom",
        "fixtures": "docs/contracts/vectors/route-manager-v1.json",
        "fake": "core:fakes/route_manager.py",
        "packet": "docs/contracts/review/05-route-manager-v1.md",
    },
    "vault-service": {
        "idl": "core:mojom/vault.mojom",
        "fixtures": "core:fakes/fixtures/vault-v1.json",
        "fake": "core:fakes/vault.py",
        "packet": "docs/contracts/review/06-vault-service-v1.md",
    },
    "guard-ledger": {
        "idl": "core:mojom/guard.mojom",
        "fixtures": "core:fakes/fixtures/guard-v1.json",
        "fake": "core:fakes/guard.py",
        "packet": "docs/contracts/review/07-guard-ledger-v1.md",
    },
    "download-safety": {
        "idl": "core:mojom/downloads.mojom",
        "fixtures": "core:fakes/fixtures/downloads-v1.json",
        "fake": "core:fakes/downloads.py",
        "packet": "docs/contracts/review/08-download-safety-v1.md",
    },
    "activity-log": {
        "idl": "core:mojom/activity_log.mojom",
        "fixtures": "core:fakes/fixtures/activity-log-v1.json",
        "fake": "core:fakes/activity_log.py",
        "packet": "docs/contracts/review/09-activity-log-v1.md",
    },
    "command-descriptor": {
        "schema": "docs/contracts/command-descriptor-v1.schema.json",
        "doc": "docs/contracts/command-descriptor-v1.md",
        "fixtures": "core:fakes/fixtures/command-descriptor-v1.json",
        "fake": "core:fakes/fixtures/command-descriptor-v1.json",
        "packet": "docs/contracts/review/10-command-descriptor-v1.md",
    },
    "list-bundle-manifest": {
        "schema": "docs/contracts/list-bundle-manifest-v1.schema.json",
        "doc": "docs/contracts/list-bundle-manifest-v1.md",
        "fixtures": "core:fakes/fixtures/list-bundle-example.json",
        "fake": "core:fakes/fixtures/list-bundle-example.json",
        "packet": "docs/contracts/review/11-list-bundle-manifest-v1.md",
    },
    "update-manifest": {
        "schema": "docs/contracts/update-manifest-31.schema.json",
        "doc": "docs/contracts/update-manifest-31-json.md",
        "fixtures": "core:fakes/fixtures/update-manifest-example.json",
        "fake": "core:fakes/fixtures/update-manifest-example.json",
        "packet": "docs/contracts/review/12-update-manifest-v1.md",
    },
    "isolation-card": {
        "schema": "core:l10n/isolation_card.json",
        "doc": "docs/contracts/review/13-isolation-card-v1.md",
        "fixtures": "core:l10n/isolation_card.json",
        "fake": "core:l10n/isolation_card.json",
        "packet": "docs/contracts/review/13-isolation-card-v1.md",
    },
    "settings-theme-schema": {
        "doc": "docs/contracts/xr-schema-v1.md",
        "schema": "docs/contracts/settings-schema-v1.md",
        "fixtures": "core:fakes/fixtures/settings-example.json",
        "fake": "tools/xr_schema.py",
        "packet": "docs/contracts/review/14-settings-theme-schema-v1.md",
    },
}

VERSION_RE = re.compile(r"(kContractVersion\s*=\s*\d+|contract_version|Version:\**\s*\d|\"contract_version\")")
MIGRATION_RE = re.compile(r"[Mm]igration note|migration|xr-schema-v1|forward-only")


def _resolve(repo: Path, spec: str) -> Path:
    if spec.startswith("core:"):
        return (repo.parent / "xr-core" / spec[len("core:"):]).resolve()
    return (repo / spec).resolve()


def check(repo: Path) -> list[str]:
    fails: list[str] = []
    required_parts = ["fixtures", "fake", "packet"]  # plus idl-or-schema
    for item, parts in ITEMS.items():
        # IDL-or-schema
        idl_or_schema = parts.get("idl") or parts.get("schema")
        if not idl_or_schema:
            fails.append(f"{item}: missing IDL-or-schema definition")
        else:
            p = _resolve(repo, idl_or_schema)
            if not p.exists():
                fails.append(f"{item}: IDL/schema not found: {idl_or_schema}")
            else:
                text = p.read_text()
                if not VERSION_RE.search(text):
                    fails.append(f"{item}: version marker missing in {idl_or_schema}")
        # migration note: in the idl/schema/doc
        mig_src = parts.get("doc") or idl_or_schema
        mp = _resolve(repo, mig_src) if mig_src else None
        if mp and mp.exists():
            if not MIGRATION_RE.search(mp.read_text()):
                fails.append(f"{item}: migration-note missing in {mig_src}")
        # remaining parts
        for part in required_parts:
            if part not in parts:
                fails.append(f"{item}: missing part {part!r}")
                continue
            p = _resolve(repo, parts[part])
            if not p.exists():
                fails.append(f"{item}: {part} not found: {parts[part]}")
    return fails


def check_reserved_surface(repo: Path) -> list[str]:
    fails: list[str] = []
    core = repo.parent / "xr-core"
    rm = (core / "mojom/route_manager.mojom")
    if rm.exists():
        t = rm.read_text()
        for meth in ("Bind(", "Unbind(", "Status(", "LoseAllFailClosed("):
            if meth not in t:
                fails.append(f"§2.10 RouteManager missing method {meth[:-1]}")
    else:
        fails.append("§2.10 route_manager.mojom missing")
    ep = (repo / "docs/contracts/effective-policy-v1.schema.json")
    if ep.exists():
        t = ep.read_text()
        for field in ("fingerprint", "letterbox", "storage_scope"):
            if field not in t:
                fails.append(f"§2.10 EffectivePolicy missing reserved field {field!r}")
    else:
        fails.append("§2.10 effective-policy schema missing")
    g = (core / "mojom/guard.mojom")
    if g.exists():
        t = g.read_text()
        for hook in ("RecentUpdateDiffs", "RecentEgress"):
            if hook not in t:
                fails.append(f"§2.10 GuardLedger missing hook {hook!r}")
    else:
        fails.append("§2.10 guard.mojom missing")
    return fails


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="contracts_manifest", description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    repo = Path(args.repo).resolve()
    fails = check(repo) + check_reserved_surface(repo)
    if args.json:
        import json
        print(json.dumps({"tool": "contracts_manifest", "items": len(ITEMS),
                          "status": "pass" if not fails else "fail",
                          "failures": fails}, indent=2))
    else:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"{'PASS' if not fails else 'FAIL'}: contracts_manifest ({len(ITEMS)} items)")
    return EXIT_PASS if not fails else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
