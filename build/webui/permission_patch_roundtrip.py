"""permission_patch_roundtrip.py — P15-CLOSE C7: the permission-prompt
button-order patch (xr-core patches/ui-permissions/0400-permission-prompt-order)
round-trips at the pin.

Sibling of shield_seam_roundtrip.py (P11) and patch_roundtrip.py (P7); same
laws, new seam, one extra law (order only):

  1. Fetches the exact upstream file(s) the patch modifies, at the DEPS
     chromium_rev, through build/upstream/fetch.py (the only network choke
     point). No remembered contents, no fixtures — a fetch failure is
     BLOCKED, never simulated.
  2. Assembles a throwaway git checkout holding those files at their
     Chromium paths and commits them (the "pre" state, hashed).
  3. Applies the guarded transform (anchored to a block that must occur
     exactly once) and `git diff`s: that diff IS the manifest patch.
  4. Order-only law: every added line is a preprocessor guard, a comment, or
     a line that already exists in the pinned upstream file. A new line of
     code is refused — this patch reorders, it never adds behavior.
  5. Round-trip: git apply --check on a pristine copy -> apply -> markers
     present -> git apply -R -> byte-exact compare against the pre-state.
  6. Negative: perturb the pinned anchor and assert the patch then FAILS to
     apply (bound to the pinned bytes, so upstream drift is caught).
  7. Never-list + budget: every file lives under
     chrome/browser/ui/views/permissions/ and there are at most 4 files (the
     P15 brief's C7 cap); the manifest row lists exactly those files.

Modes: --check (default) regenerates into a temp dir and byte-compares with
the committed patch (never rewrites it) · --write writes the manifest patch ·
--plant-drift perturbs the fetched anchor BEFORE the transform, which must
stop the generator with "anchor not found (upstream drift)" (the negative in
tools/negatives/p15c_c7.sh). No Chromium build is claimed (gn is absent here).
No wall clock is read.

Exit codes: 0 pass · 1 fail · 2 usage. --json for machines.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
for _p in [Path(_HERE), *_HERE.parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        sys.path.insert(0, str(_p / "upstream"))  # fetch.py — the choke point
        break

from _common import ToolError, load_deps, repo_root  # noqa: E402
from shield_seam_roundtrip import _git, _must, _sha256  # noqa: E402

PATCH_ID = "0400-permission-prompt-order"
PATCH_DIR = "ui-permissions/" + PATCH_ID
NEVER_ROOT = "chrome/browser/ui/views/permissions/"
FILE_CAP = 4  # P15-CLOSE C7: "<= 4 files under chrome/browser/ui/views/permissions/"
GUARD = "ENABLE_XR_PERMISSIONS"

TARGET = "chrome/browser/ui/views/permissions/permission_prompt_bubble_base_view.cc"
ANCHOR = """    buttons_container->AddChildView(std::move(allow_always_button));
    buttons_container->AddChildView(std::move(allow_once_button));
    buttons_container->AddChildView(std::move(block_button));
"""
REPLACEMENT = f"""#if defined({GUARD})
    // XR patch 0400 (order only): one-time first for the capabilities
    // that offer it, so keyboard focus lands on the one-time grant
    // (xr-core permissions/core/present.cc ButtonOrder; plan line 808).
    buttons_container->AddChildView(std::move(allow_once_button));
    buttons_container->AddChildView(std::move(allow_always_button));
    buttons_container->AddChildView(std::move(block_button));
#else
{ANCHOR}#endif  // {GUARD}
"""
TARGETS = [{"path": TARGET,
            "ops": [{"kind": "replace", "anchor": ANCHOR, "text": REPLACEMENT}]}]
MARKERS = [
    (TARGET, f"#if defined({GUARD})"),
    (TARGET, "XR patch 0400 (order only)"),
    (TARGET, f"#endif  // {GUARD}"),
]
_GUARD_LINE = re.compile(r"^#(if|ifdef|ifndef|else|elif|endif)\b")


def apply_ops(text: str, ops: list[dict]) -> str:
    for op in ops:
        if op["kind"] != "replace":
            raise ToolError(f"unknown op kind {op['kind']!r}")
        n = text.count(op["anchor"])
        if n == 0:
            raise ToolError("anchor not found (upstream drift): "
                            f"{op['anchor'].strip().splitlines()[0][:70]!r}")
        if n != 1:
            raise ToolError("anchor not unique (refusing to guess): "
                            f"{op['anchor'].strip().splitlines()[0][:70]!r}")
        text = text.replace(op["anchor"], op["text"], 1)
    return text


def order_only_violations(patch: str, upstream: dict[str, str]) -> list[str]:
    """Every '+' line must be a guard, a comment, blank, or an upstream line."""
    bad: list[str] = []
    cur = ""
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        s = body.strip()
        if not s or s.startswith("//") or _GUARD_LINE.match(s):
            continue
        if body not in upstream.get(cur, "").splitlines():
            bad.append(f"{cur}: added line is new code (order-only law): {s[:70]!r}")
    return bad


def manifest_files(xr_core: Path) -> list[str]:
    """The files: list of the 0400 row in patches/manifest.yaml (no yaml dep)."""
    text = (xr_core / "patches" / "manifest.yaml").read_text(encoding="utf-8")
    m = re.search(r'- id: "?' + re.escape(PATCH_ID) + r'"?\n(.*?)(?=\n  - id:|\Z)',
                  text, re.S)
    if not m:
        raise ToolError(f"manifest row {PATCH_ID} missing from patches/manifest.yaml")
    fm = re.search(r"files:\n((?:\s+- .+\n)+)", m.group(1) + "\n")
    return [ln.strip()[2:].strip() for ln in fm.group(1).splitlines()] if fm else []


def roundtrip(rev: str, xr_core: Path, plant_drift: bool) -> dict:
    files = [t["path"] for t in TARGETS]
    refusals = [p for p in files if not p.startswith(NEVER_ROOT)]
    if refusals:
        raise ToolError(f"never-list refusal (must stay {NEVER_ROOT}**): "
                        + "; ".join(refusals))
    if len(files) > FILE_CAP:
        raise ToolError(f"file budget blown: {len(files)} > {FILE_CAP} (P15 C7)")
    mf = manifest_files(xr_core)
    if sorted(mf) != sorted(files):
        raise ToolError(f"manifest row files {mf} != patch files {files}")

    from fetch import FetchError, GitilesFetchSource  # the choke point
    src = GitilesFetchSource()
    fetched: dict[str, str] = {}
    for t in TARGETS:
        try:
            fetched[t["path"]] = src.file_text(rev, t["path"])
        except FetchError as exc:
            raise ToolError(f"BLOCKED-NET: cannot fetch {t['path']} at {rev}: {exc}")
    if plant_drift:  # simulate an upstream rename of the reordered call
        fetched[TARGET] = fetched[TARGET].replace(
            "AddChildView(std::move(allow_once_button))",
            "AddChildView(std::move(allow_once_button_v2))")

    with tempfile.TemporaryDirectory(prefix="xr-perm-patch-") as tmp:
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
        pre = {str(p.relative_to(root)): _sha256(p.read_bytes())
               for p in root.rglob("*") if p.is_file() and ".git/" not in str(p)}

        for t in TARGETS:  # raises "anchor not found (upstream drift)" on drift
            (root / t["path"]).write_text(apply_ops(fetched[t["path"]], t["ops"]),
                                          encoding="utf-8")
        patch = _git(root, "diff", "--no-color", "--binary").stdout
        patch_path = Path(tmp) / f"{PATCH_ID}.patch"
        patch_path.write_text(patch, encoding="utf-8")
        _must(root, "checkout", "-q", "--", ".")

        res: dict = {
            "tool": "permission-patch-roundtrip",
            "rev": rev,
            "patch_sha256": _sha256(patch.encode()),
            "patch_bytes": len(patch.encode()),
            "files": files,
            "never_list": f"PASS (all files under {NEVER_ROOT}**)",
            "source": "real-fetch",
            "patch": patch,
        }
        fails = order_only_violations(patch, fetched)
        res["order_only"] = "PASS" if not fails else "FAIL"
        if fails:
            res["failures"] = fails
            return res

        check = _git(root, "apply", "--check", str(patch_path))
        if check.returncode != 0:
            res["apply"] = "FAIL"
            res["failures"] = [f"git apply --check refused: {(check.stderr or check.stdout).strip()}"]
            return res
        _must(root, "apply", str(patch_path))
        res["apply"] = "PASS"
        fails = [f"{p}: missing marker {n[:40]!r}" for p, n in MARKERS
                 if n not in (root / p).read_text(encoding="utf-8")]
        res["verify"] = "PASS" if not fails else "FAIL"
        if fails:
            res["failures"] = fails
            return res
        _must(root, "apply", "-R", str(patch_path))
        post = {str(p.relative_to(root)): _sha256(p.read_bytes())
                for p in root.rglob("*") if p.is_file() and ".git/" not in str(p)}
        drift = sorted(k for k, v in pre.items() if post.get(k) != v)
        leftover = sorted(set(post) - set(pre))
        res["revert_byte_exact"] = not drift and not leftover
        res["revert"] = "PASS" if res["revert_byte_exact"] else "FAIL"
        if drift or leftover:
            res["failures"] = ([f"revert drift: {k}" for k in drift]
                               + [f"residual file: {f}" for f in leftover])
            return res

        # Negative: perturb the pinned anchor -> the patch must fail to apply.
        p = root / TARGET
        original = p.read_text(encoding="utf-8")
        p.write_text(original.replace(ANCHOR, ANCHOR.replace(
            "allow_once_button", "allow_once_button /* perturbed */", 1), 1),
            encoding="utf-8")
        neg = _git(root, "apply", "--check", str(patch_path))
        p.write_text(original, encoding="utf-8")
        res["negative"] = {
            "test": "perturb the pinned anchor block, then git apply --check",
            "expected": "FAIL (patch is bound to the pinned bytes)",
            "observed": "FAIL" if neg.returncode != 0 else "PASS",
        }
        res["failures"] = [] if neg.returncode != 0 else [
            "negative did not fail: patch is NOT bound to the pinned bytes"]
        return res


def main() -> int:
    ap = argparse.ArgumentParser(prog="permission_patch_roundtrip")
    ap.add_argument("--rev", help="40-char chromium rev (default: DEPS)")
    ap.add_argument("--xr-core", default="../xr-core")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="regenerate and byte-compare with the committed patch (default)")
    mode.add_argument("--write", action="store_true",
                      help="write the regenerated patch to the manifest patch path")
    mode.add_argument("--plant-drift", action="store_true",
                      help="negative: perturb the fetched anchor before the transform")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        root = repo_root()
        rev = args.rev or str(load_deps(root).get("chromium_rev") or "")
        if len(rev) != 40:
            raise ToolError(f"unusable chromium rev {rev!r}")
        xr_core = Path(args.xr_core)
        if not xr_core.is_absolute():
            xr_core = (root / xr_core).resolve()
        committed = xr_core / "patches" / PATCH_DIR / f"{PATCH_ID}.patch"
        res = roundtrip(rev=rev, xr_core=xr_core, plant_drift=args.plant_drift)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"FAIL: {exc}")
        return 1

    patch = res.pop("patch")
    if not res.get("failures"):
        if args.write:
            committed.write_text(patch, encoding="utf-8")
            res["committed"] = "WRITTEN"
        elif not committed.is_file():
            res["committed"] = "MISSING"
            res["failures"] = [f"committed patch missing: {committed}"]
        elif committed.read_bytes() != patch.encode():
            res["committed"] = "DRIFT"
            res["failures"] = [f"committed patch differs from the regenerated one "
                               f"(sha {_sha256(committed.read_bytes())[:16]} vs "
                               f"{res['patch_sha256'][:16]}); regenerate with --write"]
        else:
            res["committed"] = "MATCH"
    ok = not res.get("failures")
    res["status"] = "pass" if ok else "fail"
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"rev            : {res['rev']}")
        print(f"patch          : {res['patch_bytes']} B  sha256 {res['patch_sha256'][:16]}…")
        print(f"files ({len(res['files'])})      : " + ", ".join(res["files"])
              + f" (cap ≤{FILE_CAP})")
        print(f"never-list     : {res['never_list']}")
        print(f"order-only     : {res.get('order_only')}")
        print(f"apply          : {res.get('apply')}")
        print(f"verify         : {res.get('verify')}")
        print(f"revert         : {res.get('revert')} (byte-exact: {res.get('revert_byte_exact')})")
        neg = res.get("negative", {})
        print(f"negative       : perturbed-anchor apply {neg.get('observed', 'n/a')} "
              f"(expected {neg.get('expected', 'FAIL')})")
        print(f"committed      : {res.get('committed', 'n/a')}")
        for f in res.get("failures", []):
            print(f"FAIL: {f}")
        print("PASS: permission patch 0400 round-trips at the pin" if ok
              else "FAIL: permission patch 0400 round-trip")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
