"""build/patching/apply.py — the XR patch applicator (`xr-patch`).

Idempotent, auditable, fail-loud (Plan L6 / §15-R1). Subcommands:
  apply   — apply all (or --id) patches: git apply --check then git apply,
            records an applicability ledger (.xr/patch-apply.json).
  verify  — report which patches are currently applied (reverse-check).
  revert  — reverse applied patches (reverse order); round-trips to original.
  lint    — validate the manifest + patchinfo + path policy (no checkout).

Safety: refuses any checkout it cannot verify is Chromium-at-pin
(src/chrome/VERSION + git HEAD == --pin); refuses patch paths outside the
allowed roots or with `..` traversal; never runs `git clean`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import (  # noqa: E402
    ToolError,
    add_common_flags,
    emit,
    load_deps,
    main_with_guard,
    mock_enabled,
    repo_root,
)
from categories import PLAN_CAPS, TOTAL_CAP, validate_category  # noqa: E402

DEFAULT_ROOTS = ["chrome/app/"]
PATCHINFO_FIELDS = ["id", "title", "owner", "category", "files",
                    "upstream-bug-if-any", "retirement plan", "rebase-notes"]


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"{path}: YAML parse failure: {exc}") from exc
    if not isinstance(data, dict):
        raise ToolError(f"{path}: top level must be a mapping")
    return data


def _git(src: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(src), *args], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def verify_checkout(checkout: Path, pin: str) -> None:
    src = checkout / "src"
    version = src / "chrome" / "VERSION"
    if not version.exists():
        raise ToolError(f"not a Chromium checkout: {version} missing (refusing; never run against a random dir)")
    if not (src / ".git").exists():
        raise ToolError(f"{src} is not a git checkout; cannot verify HEAD == pin")
    r = _git(src, "rev-parse", "HEAD")
    if r.returncode != 0 or r.stdout.strip() != pin:
        raise ToolError(f"checkout HEAD {r.stdout.strip()!r} != pin {pin!r}; refuse to apply")


def patch_files(patchdir: Path) -> list[Path]:
    files = sorted(patchdir.glob("*.patch"))
    if not files:
        raise ToolError(f"{patchdir}: no *.patch files")
    return files


def content_hash(patchdir: Path) -> str:
    h = hashlib.sha256()
    for p in patch_files(patchdir):
        h.update(p.read_bytes())
    return h.hexdigest()


def diff_paths(patchfile: Path) -> list[str]:
    """Extract `+++ b/<path>` targets (the applied-to side) from a unified diff."""
    paths: list[str] = []
    for line in patchfile.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("+++ b/"):
            paths.append(line[len("+++ b/"):].split("\t", 1)[0])
    return paths


def check_path_policy(paths: list[str], roots: list[str]) -> list[str]:
    failures: list[str] = []
    for p in paths:
        if p.startswith("/") or ".." in Path(p).parts:
            failures.append(f"path {p!r} escapes the allowed roots (absolute or .. traversal)")
            continue
        if not any(p == r.rstrip("/") or p.startswith(r) for r in roots):
            failures.append(f"path {p!r} is outside allowed roots {roots}")
    return failures


def lint_patchinfo(patchdir: Path, patch_id: str) -> list[str]:
    info = patchdir / "patchinfo.md"
    if not info.exists():
        return [f"{patchdir}: patchinfo.md missing"]
    text = info.read_text(encoding="utf-8")
    missing = [f for f in PATCHINFO_FIELDS if f"- **{f}:**" not in text]
    fails = [f"{info.name}: missing mandatory field {m!r}" for m in missing]
    if f"- **id:** {patch_id}" not in text:
        fails.append(f"{info.name}: id field must equal manifest id {patch_id!r}")
    return fails


def lint_manifest(manifest: dict[str, Any], manifest_path: Path) -> list[str]:
    fails: list[str] = []
    if manifest.get("schema_version") != 1:
        fails.append("manifest: schema_version must be 1")
    cats = manifest.get("categories")
    if not isinstance(cats, dict) or not cats:
        fails.append("manifest: categories mapping required")
    else:
        for name, meta in cats.items():
            if name not in PLAN_CAPS:
                fails.append(f"manifest: unknown category {name!r} (plan classes: {sorted(PLAN_CAPS)})")
            elif not isinstance(meta, dict) or meta.get("cap") != PLAN_CAPS[name]:
                fails.append(f"manifest: category {name!r} cap must be {PLAN_CAPS[name]!r}")
    if manifest.get("total_cap") != TOTAL_CAP:
        fails.append(f"manifest: total_cap must be {TOTAL_CAP}")

    roots = manifest.get("allowed_roots") or DEFAULT_ROOTS
    patches = manifest.get("patches")
    if not isinstance(patches, list) or not patches:
        fails.append("manifest: non-empty 'patches' list required")
        return fails

    seen: set[str] = set()
    counts: dict[str, int] = {c: 0 for c in PLAN_CAPS}
    allowed_keys = {"id", "owner", "category", "files", "dir"}
    for p in patches:
        if not isinstance(p, dict):
            fails.append("manifest: each patch must be a mapping")
            continue
        pid = p.get("id")
        if pid is not None:
            for key in p:
                if key not in allowed_keys:
                    fails.append(f"manifest: patch {pid} has unknown field {key!r} (allowed: {sorted(allowed_keys)})")
        if not isinstance(pid, str) or not pid:
            fails.append("manifest: patch missing string 'id'")
            continue
        if pid in seen:
            fails.append(f"manifest: duplicate patch id {pid!r}")
        seen.add(pid)
        if not p.get("owner"):
            fails.append(f"manifest: patch {pid} missing 'owner'")
        cat = p.get("category")
        fails.extend(validate_category(cat) if cat else [f"manifest: patch {pid} missing 'category'"])
        files = p.get("files")
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            fails.append(f"manifest: patch {pid} 'files' must be a list of strings")
        else:
            fails.extend(check_path_policy(files, roots))
        d = p.get("dir")
        if not d:
            fails.append(f"manifest: patch {pid} missing 'dir'")
            continue
        patchdir = manifest_path.parent / d
        if not patchdir.is_dir():
            fails.append(f"manifest: patch {pid} dir {d} not found")
            continue
        fails.extend(lint_patchinfo(patchdir, pid))
        try:
            for pf in patch_files(patchdir):
                fails.extend(check_path_policy(diff_paths(pf), roots))
        except ToolError as e:
            fails.append(str(e))
        counts[cat] = counts.get(cat, 0) + 1 if cat else counts.get(cat, 0)

    total = len(patches)
    if total > TOTAL_CAP:
        fails.append(f"budget: {total} patches exceeds total cap {TOTAL_CAP}")
    for c, n in counts.items():
        cap = PLAN_CAPS[c]
        if cap is not None and n > cap:
            fails.append(f"budget: category {c!r} has {n} patches, cap {cap}")
    return fails


def load_ledger(checkout: Path) -> dict[str, dict[str, str]]:
    p = checkout / ".xr" / "patch-apply.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"ledger {p} corrupt: {exc}") from exc
    return data.get("applied", {})


def write_ledger(checkout: Path, applied: dict[str, dict[str, str]]) -> Path:
    d = checkout / ".xr"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "patch-apply.json"
    p.write_text(json.dumps({"schema_version": 1, "applied": applied}, indent=2) + "\n", encoding="utf-8")
    return p


def select_patches(manifest: dict[str, Any], only_id: str | None) -> list[dict[str, Any]]:
    patches = manifest["patches"]
    if only_id:
        patches = [p for p in patches if p.get("id") == only_id]
        if not patches:
            raise ToolError(f"--id {only_id!r} not found in manifest")
    return patches


def _missing_manifest_error(manifest_path: Path) -> ToolError:
    """D2 regression (P3 T0.3): absent manifest must fail clean, never crash."""
    rev = "<unknown>"
    try:
        rev = str(load_deps(repo_root()).get("xr_core_rev", "<unknown>"))
    except ToolError:
        pass  # not run from a repo — no DEPS context to cite
    return ToolError(
        f"manifest not found at {manifest_path} (xr-core rev {rev}? run build sync)")


def cmd(args: argparse.Namespace) -> int:
    # Default checkout mirrors sync.py's `_checkout_root`: <cwd>/chromium
    # (the gclient solution root: chromium at src/, xr-core at src/xr).
    checkout = Path(args.checkout).resolve() if args.checkout else Path.cwd() / "chromium"
    if args.manifest:
        manifest_path = Path(args.manifest).resolve()
    else:
        manifest_path = checkout / "src" / "xr" / "patches" / "manifest.yaml"
    if not manifest_path.exists():
        raise _missing_manifest_error(manifest_path)
    manifest = _load_yaml(manifest_path)
    fails = lint_manifest(manifest, manifest_path)

    if args.cmd == "lint":
        return emit(args.json, {"tool": "xr-patch", "cmd": "lint", "manifest": str(manifest_path),
                                "patches": len(manifest.get("patches", []))}, failures=fails)

    if fails:
        return emit(args.json, {"tool": "xr-patch", "cmd": args.cmd}, failures=fails)

    pin = args.pin
    if not pin:
        raise ToolError("--pin is required for apply/verify/revert")
    if not mock_enabled():
        verify_checkout(checkout, pin)

    applied = load_ledger(checkout)
    results: list[dict[str, str]] = []
    ordered = list(manifest["patches"])
    if args.cmd == "revert":
        ordered = list(reversed(ordered))

    for p in select_patches(manifest, args.id if args.cmd != "revert" else args.id):
        pid = p["id"]
        patchdir = manifest_path.parent / p["dir"]
        h = content_hash(patchdir)
        src = checkout / "src"

        if args.cmd == "apply":
            if applied.get(pid, {}).get("content_hash") == h:
                results.append({"id": pid, "status": "no-op (already applied)"})
                continue
            recovered = False
            for pf in patch_files(patchdir):
                r = _git(src, "apply", "--check", str(pf))
                if r.returncode != 0:
                    rr = _git(src, "apply", "--reverse", "--check", str(pf))
                    if rr.returncode == 0:
                        recovered = True  # already applied, ledger lost -> re-record below
                        continue
                    return emit(args.json, {"tool": "xr-patch", "cmd": "apply", "patch": pid},
                                failures=[f"{pid}: does not apply cleanly —\n{r.stderr[-2000:]}"])
                r = _git(src, "apply", str(pf))
                if r.returncode != 0:
                    return emit(args.json, {"tool": "xr-patch", "cmd": "apply", "patch": pid},
                                failures=[f"{pid}: apply failed —\n{r.stderr[-2000:]}"])
            applied[pid] = {"applied_at_rev": pin, "content_hash": h}
            results.append({"id": pid, "status": "recovered (already applied)" if recovered else "applied"})

        elif args.cmd == "verify":
            state = "applied" if applied.get(pid, {}).get("content_hash") == h else "not-applied"
            results.append({"id": pid, "status": state})

        elif args.cmd == "revert":
            if applied.get(pid, {}).get("content_hash") != h:
                results.append({"id": pid, "status": "not-applied (skip)"})
                continue
            for pf in reversed(patch_files(patchdir)):
                r = _git(src, "apply", "--reverse", str(pf))
                if r.returncode != 0:
                    return emit(args.json, {"tool": "xr-patch", "cmd": "revert", "patch": pid},
                                failures=[f"{pid}: revert failed —\n{r.stderr[-2000:]}"])
            del applied[pid]
            results.append({"id": pid, "status": "reverted"})

    ledger_path = write_ledger(checkout, applied)
    return emit(args.json, {"tool": "xr-patch", "cmd": args.cmd, "results": results,
                            "ledger": str(ledger_path)})


def main() -> None:
    parser = argparse.ArgumentParser(prog="xr-patch",
                                     description="Apply/verify/revert XR patches against a pinned checkout; or lint the manifest.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, help_ in [("apply", "apply patches (idempotent)"), ("verify", "report applied state"),
                        ("revert", "reverse applied patches"), ("lint", "validate manifest (no checkout)")]:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--checkout", help="checkout root (contains src/)")
        sp.add_argument("--manifest", help="manifest path (default: <checkout>/src/xr/patches/manifest.yaml)")
        sp.add_argument("--pin", help="chromium pin (40-char SHA); required for apply/verify/revert")
        sp.add_argument("--id", help="operate on a single patch id")
        sp.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()
    main_with_guard(lambda: cmd(args))


if __name__ == "__main__":
    main()
