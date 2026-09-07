"""genpatch.py — the P4 code-level proof: a REAL patch round-trip at the pin.

What this does, and why it is evidence rather than a demo:

  1. Fetches the exact files the 0042-seam-hook candidate patch touches, at
     the DEPS `chromium_rev`, through build/upstream/fetch.py (the only
     network choke point). No remembered contents, no fixtures — if a fetch
     fails, the run is BLOCKED, never simulated.
  2. Assembles a throwaway git checkout with those files at their Chromium
     paths and commits them (the "pre" state, hashed).
  3. Applies the spike transforms (seam_spec.py) and `git diff`s the result:
     that diff IS the candidate patch (sha256 recorded).
  4. Round-trip: `git apply --check` on a pristine copy -> apply -> verify
     every expected marker is present -> `git apply -R` -> byte-exact compare
     of every file against the pre-state hashes.
  5. Negative: perturbs one fetched byte and asserts the patch then FAILS to
     apply with a reason (proves the patch is bound to the pin, so upstream
     drift at promotion time is caught).
  6. Never-list: refuses any target outside chrome/browser/** (§12.7).

Exit codes: 0 pass · 1 fail · 2 usage. --json for machines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        sys.path.insert(0, str(_p / "upstream"))   # fetch.py — the choke point
        break

from _common import ToolError, load_deps, repo_root  # noqa: E402

import seam_spec  # noqa: E402

DEFAULT_OUT = Path("work/spike-checkout")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), text=True,
                          capture_output=True)


def _must(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    r = _git(cwd, *args)
    if r.returncode != 0:
        raise ToolError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


class Checkout:
    """A throwaway git repo holding the pinned files at their Chromium paths."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        _must(self.root, "init", "-q")
        _must(self.root, "config", "user.email", "spike@xr.test")
        _must(self.root, "config", "user.name", "xr-spike-genpatch")

    def write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def commit_all(self, msg: str) -> None:
        _must(self.root, "add", "-A")
        _must(self.root, "commit", "-qm", msg)

    def hashes(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and ".git/" not in str(p.relative_to(self.root)):
                out[str(p.relative_to(self.root))] = _sha256(p.read_bytes())
        return out


def fetch_pinned(rev: str, files: list[str]) -> dict[str, str]:
    """Fetch pinned-rev sources through the allowlisted choke point."""
    from fetch import FetchError, GitilesFetchSource  # the choke point
    src = GitilesFetchSource()
    got: dict[str, str] = {}
    for f in files:
        try:
            got[f] = src.file_text(rev, f)
        except FetchError as exc:
            raise ToolError(f"BLOCKED-NET: cannot fetch {f} at {rev}: {exc}") from exc
    return got


def apply_ops(text: str, ops: list[dict[str, Any]]) -> str:
    for op in ops:
        kind = op["kind"]
        if kind == "replace":
            if op["old"] not in text:
                raise ToolError("patch anchor not found (upstream drift): "
                                f"{op['old'][:80]!r}")
            if text.count(op["old"]) != 1:
                raise ToolError("patch anchor is not unique — refusing to guess "
                                f"which occurrence: {op['old'][:80]!r}")
            text = text.replace(op["old"], op["new"], 1)
        elif kind == "insert_after":
            if op["anchor"] not in text:
                raise ToolError("include anchor not found (upstream drift): "
                                f"{op['anchor']!r}")
            if text.count(op["anchor"]) != 1:
                raise ToolError(f"include anchor not unique: {op['anchor']!r}")
            text = text.replace(op["anchor"], op["anchor"] + "\n" + op["text"], 1)
        elif kind == "create":
            pass  # payload write, handled by the caller
        else:
            raise ToolError(f"unknown op kind {kind!r}")
    return text


def build_patch(co: Checkout, *, xr_core: Path, pinned: dict[str, str]) -> str:
    """Write payloads + transformed files into the checkout (uncommitted)."""
    payloads = seam_spec.payloads(xr_core)
    for dest, source in payloads.items():
        co.write(dest, source.read_text(encoding="utf-8"))
        # new files are untracked: `git add -N` (intent-to-add) is what makes
        # them appear in `git diff` as proper /dev/null -> b/<path> additions.
        _must(co.root, "add", "-N", dest)
    for spec in seam_spec.targets():
        if not spec["fetch"]:
            continue
        co.write(spec["path"], apply_ops(pinned[spec["path"]], spec["ops"]))
    r = _git(co.root, "diff", "--no-color", "--binary")
    return r.stdout


def verify_applied(co: Checkout) -> list[str]:
    """Assertions about the post-apply tree (the 'verify' in apply/verify)."""
    fails: list[str] = []
    nav = (co.root / seam_spec.NAVIGATOR).read_text(encoding="utf-8")
    for needle in ("chrome/browser/xr/xr_identity.h",
                   "xr::SiteInstanceForIdentity",
                   "ENABLE_XR_SPIKE"):
        if needle not in nav:
            fails.append(f"{seam_spec.NAVIGATOR}: missing {needle!r} after apply")
    if "xr::SiteInstanceForIdentity" not in nav or "params.opener" not in nav:
        fails.append(f"{seam_spec.NAVIGATOR}: SiteInstance block not rewritten")
    build = (co.root / seam_spec.NAVIGATOR_BUILD).read_text(encoding="utf-8")
    if "chrome/browser/xr:identity_seam" not in build:
        fails.append(f"{seam_spec.NAVIGATOR_BUILD}: spike dep not wired")
    for p in (seam_spec.HOOK_HEADER, seam_spec.HOOK_SOURCE,
              seam_spec.OVERRIDE_HEADER, seam_spec.OVERRIDE_SOURCE):
        if not (co.root / p).is_file():
            fails.append(f"{p}: payload not present after apply")
    return fails


def roundtrip(*, rev: str, xr_core: Path, out: Path) -> dict[str, Any]:
    spec = seam_spec.targets()
    refusals = seam_spec.check_paths([t["path"] for t in spec]
                                     + list(seam_spec.payloads(xr_core).keys()))
    if refusals:
        raise ToolError("never-list refusal: " + "; ".join(refusals))

    fetched = fetch_pinned(rev, [t["path"] for t in spec if t["fetch"]])
    with tempfile.TemporaryDirectory(prefix="xr-genpatch-") as tmp:
        co = Checkout(Path(tmp) / "checkout")
        for path, text in fetched.items():
            co.write(path, text)
        co.commit_all("pinned upstream state")
        pre = co.hashes()

        patch = build_patch(co, xr_core=xr_core, pinned=fetched)
        _must(co.root, "checkout", "-q", "--", ".")   # back to pristine
        for p in seam_spec.payloads(xr_core):
            pth = co.root / p
            if pth.exists():
                pth.unlink()
        patch_path = out / "0042-seam-hook.patch"
        out.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(patch, encoding="utf-8")

        check = _git(co.root, "apply", "--check", str(patch_path))
        applied = check.returncode == 0
        apply_msg = (check.stderr or check.stdout).strip()
        result: dict[str, Any] = {
            "tool": "genpatch", "rev": rev,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "patch_sha256": _sha256(patch.encode()),
            "patch_bytes": len(patch.encode()),
            "files": {},
            "never_list": "PASS (targets restricted to chrome/browser/**)",
            "source": "real-fetch",
        }
        for path, text in fetched.items():
            result["files"][path] = {
                "bytes": len(text.encode()), "sha256": _sha256(text.encode())}
        for dest, src in seam_spec.payloads(xr_core).items():
            result["files"][dest] = {
                "bytes": src.stat().st_size,
                "sha256": _sha256(src.read_bytes()),
                "added_by": "spike payload (xr-core)"}

        if not applied:
            result["apply"] = "FAIL"
            result["failures"] = [f"git apply --check refused: {apply_msg}"]
            return result

        a = _must(co.root, "apply", str(patch_path))
        result["apply"] = "PASS"
        verify = verify_applied(co)
        result["verify"] = "PASS" if not verify else "FAIL"
        if verify:
            result["failures"] = verify
            return result

        r = _must(co.root, "apply", "-R", str(patch_path))
        post = co.hashes()
        drift = {k: (v, post.get(k)) for k, v in pre.items() if post.get(k) != v}
        leftover = sorted(set(post) - set(pre))
        result["revert"] = "PASS" if not drift and not leftover else "FAIL"
        result["revert_byte_exact"] = not drift and not leftover
        if drift or leftover:
            result["failures"] = ([f"revert drift: {k}" for k in drift]
                                  + [f"residual file: {k}" for k in leftover])
            return result

        # Negative: perturb the pinned bytes INSIDE a hunk (git apply tolerates
        # a shifted line offset, so perturbing the top of the file proves
        # nothing — perturbing the anchor does) and require the patch to fail.
        target = seam_spec.NAVIGATOR
        p = co.root / target
        original = p.read_text(encoding="utf-8")
        # Pick a context line that really sits inside the hunk (git only
        # includes 3 lines of context around the change, so perturbing the
        # first line of the old block would prove nothing — it is outside the
        # hunk and git apply never looks at it).
        anchor_line = seam_spec.SITEINSTANCE_OLD.splitlines()[2]
        if original.count(anchor_line) != 1:
            result["negative"] = {
                "observed": "INCONCLUSIVE",
                "reason": f"perturbation target not unique in {target}: "
                          f"{anchor_line.strip()!r}"}
            result["failures"] = ["negative inconclusive: perturbation target "
                                  "is not unique — cannot attribute the result"]
            return result
        p.write_text(original.replace(
            anchor_line, anchor_line + " /* perturbed */", 1), encoding="utf-8")
        neg = _git(co.root, "apply", "--check", str(patch_path))
        p.write_text(original, encoding="utf-8")
        result["negative"] = {
            "test": "perturb a pinned line inside the patch's hunk context, "
                    "then git apply --check",
            "perturbed": f"{target}: {anchor_line.strip()} -> "
                         f"{anchor_line.strip()} /* perturbed */",
            "expected": "FAIL (the patch is bound to the pinned bytes, so "
                        "upstream drift at promotion time is detectable)",
            "observed": "FAIL" if neg.returncode != 0 else "PASS",
            "reason": (neg.stderr or neg.stdout).strip().splitlines()[:2],
        }
        result["failures"] = [] if neg.returncode != 0 else [
            "negative did not fail: the patch is NOT bound to the pinned bytes"]
        return result


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="genpatch",
        description="Real apply/verify/revert round-trip of the P4 seam-hook "
                    "candidate patch against pinned-rev Chromium files.")
    ap.add_argument("--rev", help="40-char chromium rev (default: DEPS)")
    ap.add_argument("--xr-core", default="../xr-core",
                    help="path to the xr-core checkout with spike/identity_seam")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="artifact dir")
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
        out = Path(args.out)
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
        print(f"never-list     : {res['never_list']}")
        for f, meta in res["files"].items():
            print(f"  {f:<56} {meta['bytes']:>8} B")
        print(f"apply          : {res.get('apply')}")
        print(f"verify         : {res.get('verify')}")
        print(f"revert         : {res.get('revert')} (byte-exact: "
              f"{res.get('revert_byte_exact')})")
        if "negative" in res:
            n = res["negative"]
            print(f"negative       : expected {n['expected']}, observed {n['observed']}")
        for f in res.get("failures", []):
            print(f"FAIL: {f}")
        print(f"{'PASS' if ok else 'FAIL'}: genpatch round-trip")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
