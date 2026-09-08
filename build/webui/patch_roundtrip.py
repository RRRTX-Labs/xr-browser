"""patch_roundtrip.py — the P7 code-level proof: the ≤12-file chrome/browser/ui
ui-skeleton patch round-trips at the pin.

Mirrors build/spike/genpatch.py (P4's proof) but for the P7 UI-hook set. It:

  1. Fetches the exact upstream files the patch modifies, at the DEPS
     chromium_rev, through build/upstream/fetch.py (the only network choke
     point). No remembered contents, no fixtures — a fetch failure is
     BLOCKED, never simulated.
  2. Assembles a throwaway git checkout holding those files at their Chromium
     paths and commits them (the "pre" state, hashed).
  3. Applies the ui-skeleton transforms (hook one-liners, guarded, anchored to
     a UNIQUE line each) + materializes the new chrome/browser/ui/xr/* payload
     sources from the patch dir, then `git diff`s: that diff IS the manifest
     patch (sha256 recorded, written to the manifest patch path).
  4. Round-trip: git apply --check on a pristine copy -> apply -> verify every
     expected marker is present -> git apply -R -> byte-exact compare of every
     file against the pre-state hashes.
  5. Negative: perturb a fetched anchor line and assert the patch then FAILS
     to apply (the patch is bound to the pin, so upstream drift is caught).
  6. Never-list: refuses any target outside chrome/browser/ui/** (§12.7).

Exit codes: 0 pass · 1 fail · 2 usage. --json for machines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in [Path(_HERE), *_HERE.parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        sys.path.insert(0, str(_p / "upstream"))  # fetch.py — the choke point
        break

from _common import ToolError, load_deps, repo_root  # noqa: E402

PATCH_ID = "0100-ui-skeleton"
NEVER_ROOT = "chrome/browser/ui/"

# Upstream hook transforms. Each `anchor` MUST occur exactly once in the
# pinned file (asserted); `insert_after` appends the hook line after it.
TARGETS: list[dict] = [
    {"path": "chrome/browser/ui/views/BUILD.gn", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '    "//chrome/browser/ui:layout_constants",',
         "text": '    "//chrome/browser/ui/xr",'}]},
    {"path": "chrome/browser/ui/views/toolbar/app_menu.cc", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '#include "chrome/browser/ui/views/toolbar/app_menu.h"',
         "text": '#include "chrome/browser/ui/xr/xr_command_bridge.h"'},
        {"kind": "insert_after",
         "anchor": "void AppMenu::ExecuteCommand(int command_id, int mouse_event_flags) {",
         "text": '  xr::XrCommandBridge::OnAppMenuCommand(command_id, "menu");'}]},
    {"path": "chrome/browser/ui/views/toolbar/toolbar_view.cc", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '#include "chrome/browser/ui/views/toolbar/toolbar_view.h"',
         "text": '#include "chrome/browser/ui/xr/xr_command_bridge.h"'},
        {"kind": "insert_after",
         "anchor": "void ToolbarView::Init() {",
         "text": "  xr::XrCommandBridge::RegisterToolbarSlots();"}]},
    {"path": "chrome/browser/ui/views/frame/browser_frame_view.cc", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '#include "chrome/browser/ui/views/frame/browser_frame_view.h"',
         "text": '#include "chrome/browser/ui/xr/xr_identity_color_bar.h"'},
        {"kind": "insert_after",
         "anchor": "void BrowserFrameView::OnTabStripStateChanged() {",
         "text": "  xr::XrIdentityColorBar::OnTabStripStateChanged("
                 "xr::XrIdentityColorBar::PinnedActiveIdentity(), "
                 "xr::XrIdentityColorBar::PinnedTrustTier());"}]},
]

# The post-apply markers `verify` looks for (proves the patch did the job).
MARKERS = [
    ("chrome/browser/ui/views/BUILD.gn", '    "//chrome/browser/ui/xr",'),
    ("chrome/browser/ui/views/toolbar/app_menu.cc",
     "  xr::XrCommandBridge::OnAppMenuCommand(command_id, \"menu\");"),
    ("chrome/browser/ui/views/toolbar/toolbar_view.cc",
     "  xr::XrCommandBridge::RegisterToolbarSlots();"),
    ("chrome/browser/ui/views/frame/browser_frame_view.cc",
     "xr::XrIdentityColorBar::OnTabStripStateChanged("),
]

PAYLOAD_PREFIX = "chrome/browser/ui/xr/"


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _git(cwd: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=str(cwd), text=True, capture_output=True)


def _must(cwd: Path, *a: str) -> subprocess.CompletedProcess:
    r = _git(cwd, *a)
    if r.returncode != 0:
        raise ToolError(f"git {' '.join(a)} failed: {r.stderr.strip()}")
    return r


def payloads(xr_core: Path) -> dict[str, str]:
    base = xr_core / "patches" / "ui-skeleton" / PATCH_ID / "payload"
    out: dict[str, str] = {}
    for p in sorted(base.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(base))
            if not rel.startswith(PAYLOAD_PREFIX):
                raise ToolError(f"payload path outside {PAYLOAD_PREFIX}: {rel}")
            out[rel] = p.read_text(encoding="utf-8")
    if not out:
        raise ToolError(f"no payload sources under {base}")
    return out


def apply_ops(text: str, ops: list[dict]) -> str:
    for op in ops:
        if op["kind"] != "insert_after":
            raise ToolError(f"unknown op kind {op['kind']!r}")
        if op["anchor"] not in text:
            raise ToolError("anchor not found (upstream drift): "
                            f"{op['anchor'][:70]!r}")
        if text.count(op["anchor"]) != 1:
            raise ToolError(f"anchor not unique (refusing to guess): "
                            f"{op['anchor'][:70]!r}")
        text = text.replace(op["anchor"], op["anchor"] + "\n" + op["text"], 1)
    return text


def roundtrip(rev: str, xr_core: Path, out: Path) -> dict:
    all_paths = [t["path"] for t in TARGETS if t["fetch"]] + list(payloads(xr_core))
    refusals = [p for p in all_paths if not p.startswith(NEVER_ROOT)]
    if refusals:
        raise ToolError("never-list refusal (must stay chrome/browser/ui/**): "
                        + "; ".join(refusals))

    from fetch import FetchError, GitilesFetchSource  # the choke point
    src = GitilesFetchSource()
    fetched: dict[str, str] = {}
    for t in TARGETS:
        if not t["fetch"]:
            continue
        try:
            fetched[t["path"]] = src.file_text(rev, t["path"])
        except FetchError as exc:
            raise ToolError(f"BLOCKED-NET: cannot fetch {t['path']} at {rev}: {exc}")
        for op in t["ops"]:
            if fetched[t["path"]].count(op["anchor"]) != 1:
                raise ToolError(f"anchor not unique in {t['path']}: {op['anchor'][:70]!r}")

    with tempfile.TemporaryDirectory(prefix="xr-ui-patch-") as tmp:
        root = Path(tmp) / "co"
        root.mkdir()
        _must(root, "init", "-q")
        _must(root, "config", "user.email", "spike@xr.test")
        _must(root, "config", "user.name", "xr-patch-genpatch")
        for path, text in fetched.items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text, encoding="utf-8")
        _must(root, "add", "-A")
        _must(root, "commit", "-qm", "pinned upstream state")
        pre: dict[str, str] = {
            str(p.relative_to(root)): _sha256(p.read_bytes())
            for p in root.rglob("*") if p.is_file() and ".git/" not in str(p)}

        # Build the post state: apply ops + materialize payloads (untracked).
        for t in TARGETS:
            if not t["fetch"]:
                continue
            (root / t["path"]).write_text(apply_ops(fetched[t["path"]], t["ops"]),
                                          encoding="utf-8")
        for dest, text in payloads(xr_core).items():
            (root / dest).parent.mkdir(parents=True, exist_ok=True)
            (root / dest).write_text(text, encoding="utf-8")
            _must(root, "add", "-N", dest)
        patch = _git(root, "diff", "--no-color", "--binary").stdout

        out.mkdir(parents=True, exist_ok=True)
        patch_path = out / f"{PATCH_ID}.patch"
        patch_path.write_text(patch, encoding="utf-8")

        # Round-trip on a pristine copy.
        _must(root, "checkout", "-q", "--", ".")
        for dest in payloads(xr_core):
            pth = root / dest
            if pth.exists():
                pth.unlink()
        res: dict = {
            "tool": "ui-skeleton-patch-roundtrip",
            "rev": rev,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "patch_sha256": _sha256(patch.encode()),
            "patch_bytes": len(patch.encode()),
            "hook_files": [t["path"] for t in TARGETS if t["fetch"]],
            "payload_files": sorted(payloads(xr_core)),
            "never_list": "PASS (all files under chrome/browser/ui/**)",
            "source": "real-fetch",
        }

        check = _git(root, "apply", "--check", str(patch_path))
        if check.returncode != 0:
            res["apply"] = "FAIL"
            res["failures"] = [f"git apply --check refused: {(check.stderr or check.stdout).strip()}"]
            return res
        _must(root, "apply", str(patch_path))
        res["apply"] = "PASS"
        fails = []
        for path, needle in MARKERS:
            if needle not in (root / path).read_text(encoding="utf-8"):
                fails.append(f"{path}: missing marker {needle[:40]!r}")
        for dest in payloads(xr_core):
            if not (root / dest).is_file():
                fails.append(f"{dest}: payload not present after apply")
        res["verify"] = "PASS" if not fails else "FAIL"
        if fails:
            res["failures"] = fails
            return res
        _must(root, "apply", "-R", str(patch_path))
        post = {str(p.relative_to(root)): _sha256(p.read_bytes())
                for p in root.rglob("*") if p.is_file() and ".git/" not in str(p)}
        drift = {k: (v, post.get(k)) for k, v in pre.items() if post.get(k) != v}
        leftover = sorted(set(post) - set(pre))
        res["revert"] = "PASS" if not drift and not leftover else "FAIL"
        res["revert_byte_exact"] = not drift and not leftover
        if drift or leftover:
            res["failures"] = ([f"revert drift: {k}" for k in drift]
                               + [f"residual file: {f}" for f in leftover])
            return res

        # Negative: perturb a pinned anchor line -> the patch must fail to apply.
        target = "chrome/browser/ui/views/toolbar/app_menu.cc"
        anchor = "void AppMenu::ExecuteCommand(int command_id, int mouse_event_flags) {"
        p = root / target
        original = p.read_text(encoding="utf-8")
        if original.count(anchor) != 1:
            res["failures"] = ["negative inconclusive: anchor not unique"]
            return res
        p.write_text(original.replace(anchor, anchor + " /* perturbed */", 1),
                     encoding="utf-8")
        neg = _git(root, "apply", "--check", str(patch_path))
        p.write_text(original, encoding="utf-8")
        res["negative"] = {
            "test": "perturb a pinned anchor line, then git apply --check",
            "perturbed": f"{target}: ExecuteCommand() {anchor[:30]}… + perturbed",
            "expected": "FAIL (patch is bound to the pinned bytes)",
            "observed": "FAIL" if neg.returncode != 0 else "PASS",
            "reason": (neg.stderr or neg.stdout).strip().splitlines()[:2],
        }
        res["failures"] = [] if neg.returncode != 0 else [
            "negative did not fail: patch is NOT bound to the pinned bytes"]
        return res


def main() -> int:
    ap = argparse.ArgumentParser(prog="patch_roundtrip")
    ap.add_argument("--rev", help="40-char chromium rev (default: DEPS)")
    ap.add_argument("--xr-core", default="../xr-core")
    ap.add_argument("--out", default="", help="artifact dir (default: the manifest patch dir)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        root = repo_root()
        deps = load_deps(root)
        rev = args.rev or str(deps.get("chromium_rev") or "")
        if len(rev) != 40:
            raise ToolError(f"unusable chromium rev {rev!r}")
        xr_core = Path(args.xr_core)
        if not xr_core.is_absolute():
            xr_core = (root / xr_core).resolve()
        out = Path(args.out) if args.out else (
            xr_core / "patches" / "ui-skeleton" / PATCH_ID)
        if not out.is_absolute():
            out = root / out
        res = roundtrip(rev=rev, xr_core=xr_core, out=out)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    ok = not res.get("failures")
    res["status"] = "pass" if ok else "fail"
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"rev            : {res['rev']}")
        print(f"patch          : {res['patch_bytes']} B  sha256 {res['patch_sha256'][:16]}…")
        print(f"hook files ({len(res['hook_files'])}): " + ", ".join(res["hook_files"]))
        print(f"payload files ({len(res['payload_files'])}): " + ", ".join(res["payload_files"]))
        print(f"total files    : {len(res['hook_files']) + len(res['payload_files'])} (cap ≤12)")
        print(f"never-list     : {res['never_list']}")
        print(f"apply          : {res.get('apply')}")
        print(f"verify         : {res.get('verify')}")
        print(f"revert         : {res.get('revert')} (byte-exact: {res.get('revert_byte_exact')})")
        if "negative" in res:
            n = res["negative"]
            print(f"negative       : expected {n['expected']}, observed {n['observed']}")
        for f in res.get("failures", []):
            print(f"FAIL: {f}")
        print(f"{'PASS' if ok else 'FAIL'}: ui-skeleton patch round-trip")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
