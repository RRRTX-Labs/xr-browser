"""build/upstream/retirements.py — the seam-retirement ledger (P3-T7, §12.5).

"Seams retired" is the reward metric (§12.5: "every upstreamed patch is one
we stop maintaining"). The ledger records every patch removal:
  {id, rev_retired_at, mechanism: upstreamed|obsoleted|dropped-with-review,
   evidence, note, retired_at, retired_by}

LAW: `xr-patch retire` (build/patching/apply.py) is the ONLY sanctioned
removal path — it writes the ledger entry AND removes the patch in one
operation. A removal without a ledger entry fails `retirement-lint` (CI):
when the xr-core manifest's git history is available, every historical
removal of a patch id must have a ledger row.

CLI (./scripts/build retire): list | lint.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard, repo_root  # noqa: E402

LEDGER_PATH = Path("build/upstream/retirements.json")
MECHANISMS = ("upstreamed", "obsoleted", "dropped-with-review")
ID_LINE = re.compile(r'^\s*-\s*id:\s*"?([A-Za-z0-9_.-]+)"?\s*$')


def load_ledger(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    p = root / LEDGER_PATH
    if not p.exists():
        return {"schema_version": 1, "retirements": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ToolError(f"retirements ledger corrupt: {exc}") from exc
    return data


def save_ledger(root: Path, ledger: dict[str, Any]) -> Path:
    p = root / LEDGER_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return p


def append_retirement(root: Path, *, patch_id: str, mechanism: str,
                      evidence: str, note: str, rev_retired_at: str,
                      retired_by: str) -> dict[str, Any]:
    """Validate + append one ledger row (called by xr-patch retire)."""
    if mechanism not in MECHANISMS:
        raise ToolError(f"mechanism must be one of {MECHANISMS} (got {mechanism!r})")
    if not evidence.strip():
        raise ToolError("evidence required (upstream CL / bug / obsolescence reference)")
    if not note.strip():
        raise ToolError("note required (the user-visible consequence + review entry, §12.3)")
    ledger = load_ledger(root)
    ids = [r["id"] for r in ledger["retirements"]]
    if patch_id in ids:
        raise ToolError(f"ledger already has a retirement for {patch_id!r}")
    row = {
        "id": patch_id,
        "rev_retired_at": rev_retired_at,
        "mechanism": mechanism,
        "evidence": evidence,
        "note": note,
        "retired_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "retired_by": retired_by,
    }
    ledger["retirements"].append(row)
    save_ledger(root, ledger)
    return row


def remove_patch_from_manifest(manifest_path: Path, patch_id: str) -> None:
    """Surgical text-level removal of one patch block (comments preserved).
    Verified by re-parsing afterwards."""
    import yaml
    text = manifest_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    removed = False
    while i < len(lines):
        m = ID_LINE.match(lines[i])
        if m and m.group(1) == patch_id and lines[i].startswith(("  - id:", "- id:")):
            # skip until the next patch entry at the same indent or end of list
            indent = len(lines[i]) - len(lines[i].lstrip())
            j = i + 1
            while j < len(lines):
                lj = lines[j]
                if lj.strip().startswith("- id:") and (len(lj) - len(lj.lstrip())) == indent:
                    break
                if not lj.startswith(" " * (indent + 1)) and lj.strip() and not lj.strip().startswith("-"):
                    break
                j += 1
            out.extend(lines[:i])
            out.extend(lines[j:])
            removed = True
            break
        i += 1
    if not removed:
        raise ToolError(f"patch id {patch_id!r} not found in {manifest_path}")
    new_text = "".join(out)
    data = yaml.safe_load(new_text)
    if not isinstance(data, dict):
        raise ToolError("manifest surgery failed validation (not a mapping)")
    remaining = data.get("patches") or []
    if any(p.get("id") == patch_id for p in remaining):
        raise ToolError("manifest surgery failed validation (id still present)")
    if len(remaining) != len((yaml.safe_load(text) or {}).get("patches", []) or []) - 1:
        raise ToolError("manifest surgery failed validation (wrong patch count)")
    manifest_path.write_text(new_text, encoding="utf-8")


def historical_removals(xr_core_dir: Path) -> tuple[bool, list[str]]:
    """(history_available, patch ids removed from manifest.yaml across git
    history). history_available=False when the manifest isn't in a git repo
    (fixture dirs) — the lint notes the skip, never silent."""
    r = subprocess.run(["git", "-C", str(xr_core_dir), "log", "-p", "--follow",
                        "--", "patches/manifest.yaml"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return False, []
    removed_ever: set[str] = set()
    for line in r.stdout.splitlines():
        if line[:1] != "-":
            continue
        m = ID_LINE.match(line[1:])
        if m:
            removed_ever.add(m.group(1))
    # ids ever removed AND absent from the current manifest need a ledger row;
    # re-added ids (still present) are active and exempt
    return True, sorted(removed_ever)


def lint(root: Path | None = None, xr_core_dir: Path | None = None) -> list[str]:
    """retirement-lint: schema + linkage + removal-without-ledger detection."""
    root = root or repo_root()
    fails: list[str] = []
    ledger = load_ledger(root)
    if ledger.get("schema_version") != 1:
        fails.append("ledger schema_version must be 1")
    rows = ledger.get("retirements", [])
    seen: set[str] = set()
    for row in rows:
        rid = row.get("id")
        if rid in seen:
            fails.append(f"duplicate ledger row for {rid!r}")
        seen.add(rid)
        if row.get("mechanism") not in MECHANISMS:
            fails.append(f"row {rid}: mechanism must be one of {MECHANISMS}")
        for f in ("evidence", "note", "rev_retired_at", "retired_at", "retired_by"):
            if not row.get(f):
                fails.append(f"row {rid}: missing {f!r}")

    # linkage: retired ids must NOT be in the current manifest
    xr_core_dir = xr_core_dir or (root.parent / "xr-core")
    manifest = xr_core_dir / "patches" / "manifest.yaml"
    if manifest.exists():
        import yaml
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        current = {p.get("id") for p in (data.get("patches") or [])}
        for row in rows:
            if row["id"] in current:
                fails.append(f"row {row['id']}: still present in the manifest — "
                             "retirement is incomplete (remove via xr-patch retire)")
        # removal-without-ledger (needs history; noted otherwise)
        has_hist, hist = historical_removals(xr_core_dir)
        if has_hist:
            for rid in hist:
                if rid not in seen and rid not in current:
                    fails.append(f"patch {rid!r} was removed from the manifest without a "
                                 "ledger entry — the ONLY sanctioned removal path is "
                                 "`xr-patch retire` (P3-T7 law)")
        else:
            print("note: xr-core manifest history unavailable — removal-without-ledger "
                  "cross-check skipped (not silent)")
    else:
        print(f"note: manifest not found at {manifest} — linkage checks skipped "
              "(pass --xr-core for the full lint)")
    return fails


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-retire",
        description="Seam-retirement ledger: list | lint (the only sanctioned "
                    "removal path is `xr-patch retire`).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list ledger rows")
    lint_p = sub.add_parser("lint", help="retirement-lint (CI gate)")
    lint_p.add_argument("--xr-core", default=None, help="xr-core checkout path")
    args = parser.parse_args()

    root = repo_root()
    if args.cmd == "list":
        ledger = load_ledger(root)
        if not ledger["retirements"]:
            print("(no retirements recorded — the documented zero baseline)")
        for row in ledger["retirements"]:
            print(f"{row['id']:<28} {row['mechanism']:<20} retired_at {row['rev_retired_at'][:12]}… "
                  f"({row['retired_at']})")
        return 0

    fails = lint(root, Path(args.xr_core) if args.xr_core else None)
    for f in fails:
        print(f"FAIL: {f}")
    print(f"{'PASS' if not fails else 'FAIL'}: retirement-lint "
          f"({len(load_ledger(root)['retirements'])} ledger rows)")
    return 1 if fails else 0


if __name__ == "__main__":
    main_with_guard(lambda: main())
