"""build/sbom/emit_sbom.py — build-time SBOM emission (P2-T9).

Parses `gn desc <out> //chrome:chrome --libs` + `--buildconfig` output
(fixture or real mode), walks `third_party/*/DEPS`, and (optional,
empty-tolerant) `cargo metadata`, then emits a **CycloneDX 1.6** document.

Honesty (L5): licenses are NOASSERTION unless a pinned eval states them —
full dep-graph license resolution is P9-T9. Determinism: serialNumber is
uuid5 over the sorted component list (no timestamps).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, add_common_flags, emit, main_with_guard, mock_enabled, repo_root  # noqa: E402

NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://rrrtx.example/sbom")
TARGET_RE = re.compile(r"^(\S+?):(\S+)\s*$")


def parse_gn_libs(text: str) -> list[str]:
    """`gn desc --libs` lines like `//base:base` -> component names."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("//") or ":" in line:
            out.append(line)
    return out


def third_party_components(checkout: Path) -> list[dict]:
    comps = []
    tp = checkout / "src" / "third_party"
    if not tp.is_dir():
        return comps
    for deps in sorted(tp.rglob("DEPS")):
        name = deps.parent.relative_to(tp).as_posix() or "root"
        has_license = (deps.parent / "LICENSE").exists() or (deps.parent / "LICENSE.txt").exists()
        comps.append({"name": f"third_party/{name}", "has_license_file": has_license})
    return comps


def cargo_components(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []  # empty-tolerant: missing/invalid cargo metadata yields zero components
    pkgs = data.get("packages") if isinstance(data, dict) else []
    out = []
    for p in pkgs:
        if not isinstance(p, dict):
            continue
        comp = {"name": p["name"], "version": p["version"]}
        lic = p.get("license")
        if isinstance(lic, str) and lic.strip():
            comp["licenses"] = [{"license": {"name": lic.strip()}}]
        out.append(comp)
    return out


def build_sbom(version: dict, argset: str, targets: list[str], tp: list[dict], cargo: list[dict]) -> dict:
    components = []
    for t in targets:
        components.append({"type": "library", "name": t, "version": version["full"],
                           "licenses": [{"license": {"name": "NOASSERTION"}}]})
    for c in tp:
        components.append({"type": "library", "name": c["name"], "version": version["full"],
                           "licenses": [{"license": {"name": "NOASSERTION"}}]})
    for c in cargo:
        components.append({"type": "library", "name": c["name"], "version": c["version"],
                           "licenses": c.get("licenses") or [{"license": {"name": "NOASSERTION"}}]})
    components.sort(key=lambda c: c["name"])
    digest = hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest()
    serial = str(uuid.uuid5(NS, digest))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "xr-browser",
                "version": version["full"],
                "properties": [
                    {"name": "xr:channel", "value": version["channel"]},
                    {"name": "xr:argset", "value": argset},
                    {"name": "xr:chromium_pin", "value": version.get("chromium_rev", "")},
                ],
            }
        },
        "components": components,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="build/sbom/emit_sbom.py",
                                     description="Emit a CycloneDX 1.6 SBOM from gn desc (+ third_party + cargo).")
    parser.add_argument("--fixture", action="store_true", help="emit from a built-in fixture (L1)")
    parser.add_argument("--gn-desc", help="captured `gn desc ... --libs` output file")
    parser.add_argument("--checkout", help="checkout root (L3: run gn desc live)")
    parser.add_argument("--out", help="write sbom.json to this path")
    parser.add_argument("--argset", default="xr_release.gn")
    parser.add_argument("--cargo-metadata", help="optional cargo metadata JSON (empty-tolerant)")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        from _common import load_deps
        root = repo_root()
        deps = load_deps(root)
        ver = {"full": str(deps.get("chromium_version", "")), "channel": "dev",
               "chromium_rev": str(deps.get("chromium_rev", ""))}

        targets: list[str] = []
        tp: list[dict] = []
        if args.fixture:
            targets = ["//base:base", "//third_party/abseil-cpp:absl", "//net:net", "//xr:xr_all"]
            tp = [{"name": "third_party/abseil-cpp", "has_license_file": True}]
        elif args.gn_desc:
            targets = parse_gn_libs(Path(args.gn_desc).read_text(encoding="utf-8"))
        elif args.checkout and not mock_enabled():
            from _common import run as run_cmd
            out_dir = Path(args.checkout) / "out/xr_release"
            r = run_cmd(["gn", "desc", str(out_dir), "//chrome:chrome", "--libs"], cwd=Path(args.checkout) / "src")
            targets = parse_gn_libs(r.stdout)
            tp = third_party_components(Path(args.checkout))
        elif mock_enabled():
            print("MOCK MODE — not a build: would run gn desc (no real checkout)")
            targets = ["//xr:xr_all"]

        cargo = cargo_components(Path(args.cargo_metadata) if args.cargo_metadata else None)
        sbom = build_sbom(ver, args.argset, targets, tp, cargo)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
        return emit(args.json, {"tool": "emit_sbom", "components": len(sbom["components"]),
                                "serial": sbom["serialNumber"], "out": args.out})

    main_with_guard(run)


if __name__ == "__main__":
    main()
