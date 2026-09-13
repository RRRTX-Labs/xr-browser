"""shield_seam_roundtrip.py — the P11 (DoD-10) code-level proof: the
<=8-file services/network shield-seam patch round-trips at the pin.

Sibling of build/webui/patch_roundtrip.py (P7's ui-skeleton proof); same
six laws, new seam:

  1. Fetches the exact upstream files the patch modifies, at the DEPS
     chromium_rev, through build/upstream/fetch.py (the only network choke
     point). No remembered contents, no fixtures — a fetch failure is
     BLOCKED, never simulated.
  2. Assembles a throwaway git checkout holding those files at their
     Chromium paths and commits them (the "pre" state, hashed).
  3. Applies the shield-seam transforms (guarded hook blocks, anchored to
     a UNIQUE line each) + materializes the services/network/xr/* payload
     sources from the patch dir, then `git diff`s: that diff IS the
     manifest patch (sha256 recorded, written to the manifest patch path).
  4. Round-trip: git apply --check on a pristine copy -> apply -> verify
     every expected marker is present -> git apply -R -> byte-exact
     compare of every file against the pre-state hashes.
  5. Negative: perturb a fetched anchor line and assert the patch then
     FAILS to apply (the patch is bound to the pin, so upstream drift is
     caught).
  6. Never-list: refuses any target outside services/network/** (§12.7's
     content/blink/third_party/v8 ban is untouched; the seam adds exactly
     one allowed root, recorded in patches/manifest.yaml).

Hook budget: DoD-10 says <= ~8 files for the network seam (3 upstream
hooks + 2 XR-owned payload = 5 here); the cap is asserted, not hoped.
No claim is made that Chromium BUILDS (gn is absent in this sandbox);
the proof is patch fidelity at the pinned bytes.

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

PATCH_ID = "0200-shield-network-seam"
NEVER_ROOT = "services/network/"
HOOK_BUDGET = 8  # DoD-10: "hooks <= ~8 files" — asserted below

CONSULT = """#if defined(ENABLE_XR_SHIELD)
  // P11 network seam (patch 0200): the XR Shield consult BEFORE the first
  // packet — ahead of the ResourceScheduler defer/resume path, so a
  // deferred-then-resumed request cannot slip past it. Thin data path into
  // the injected xr-core shield engine (shield/core/engine.h contract;
  // vendored adblock-rust behind the xr_shield_engine C ABI). Fail-open is
  // the posture law: no engine / dead engine / redaction failure proceeds
  // and is counted (the chip turns amber via the posture core). Route loss
  // (this call site vanishing) is fail-CLOSED and is a rebase-time marker
  // failure, never a runtime state.
  if (network::xr::XrShieldGate::ShouldBlock(*url_request_)) {
    NotifyCompleted(net::ERR_BLOCKED_BY_CLIENT);
    return;
  }
#endif  // ENABLE_XR_SHIELD"""

ATTACH = """#if defined(ENABLE_XR_SHIELD)
  // P11 network seam (patch 0200): recorded attachment point — the gate
  // counts context creation; per-context engines grow here post-v1.
  network::xr::XrShieldGate::OnNetworkContextCreated(this);
#endif  // ENABLE_XR_SHIELD"""

# Upstream hook transforms. Each `anchor` MUST occur exactly once in the
# pinned file (asserted pre-fetch and post-fetch); anchors were live-read
# at pin d04cdb24 (research-log-P11.md R3/D11).
TARGETS: list[dict] = [
    {"path": "services/network/BUILD.gn", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '    "web_transport.cc",\n    "web_transport.h",',
         "text": '    "xr/xr_shield_gate.cc",\n    "xr/xr_shield_gate.h",'}]},
    {"path": "services/network/url_loader.cc", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '#include "services/network/url_loader.h"',
         "text": '// XR shield seam (patch 0200): the consult + its error code.\n'
                 '#include "net/base/net_error_list.h"\n'
                 '#include "services/network/xr/xr_shield_gate.h"'},
        {"kind": "insert_after",
         "anchor": 'void URLLoader::ScheduleStart() {\n'
                   '  TRACE_EVENT("loading", "URLLoader::ScheduleStart",\n'
                   '              net::NetLogWithSourceToFlow('
                   'url_request_->net_log()));',
         "text": CONSULT}]},
    {"path": "services/network/network_context.cc", "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '#include "services/network/network_context.h"',
         "text": '#include "services/network/xr/xr_shield_gate.h"  '
                 '// XR shield seam (patch 0200)'},
        {"kind": "insert_after",
         "anchor": "#endif  // BUILDFLAG(IS_WIN) && DCHECK_IS_ON()",
         "text": ATTACH}]},
]

# The post-apply markers `verify` looks for (proves the patch did the job).
MARKERS = [
    ("services/network/BUILD.gn", '    "xr/xr_shield_gate.cc",'),
    ("services/network/url_loader.cc",
     "network::xr::XrShieldGate::ShouldBlock(*url_request_)"),
    ("services/network/url_loader.cc",
     "NotifyCompleted(net::ERR_BLOCKED_BY_CLIENT);"),
    ("services/network/network_context.cc",
     "network::xr::XrShieldGate::OnNetworkContextCreated(this);"),
]

PAYLOAD_PREFIX = "services/network/xr/"


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _git(cwd: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=str(cwd), text=True,
                          capture_output=True)


def _must(cwd: Path, *a: str) -> subprocess.CompletedProcess:
    r = _git(cwd, *a)
    if r.returncode != 0:
        raise ToolError(f"git {' '.join(a)} failed: {r.stderr.strip()}")
    return r


def payloads(xr_core: Path) -> dict[str, str]:
    base = xr_core / "patches" / "network-seams" / PATCH_ID / "payload"
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
    pay = payloads(xr_core)
    hooks = [t["path"] for t in TARGETS if t["fetch"]]
    refusals = [p for p in hooks + list(pay) if not p.startswith(NEVER_ROOT)]
    if refusals:
        raise ToolError("never-list refusal (must stay services/network/**): "
                        + "; ".join(refusals))
    if len(hooks) + len(pay) > HOOK_BUDGET:
        raise ToolError(f"hook budget blown: {len(hooks)} upstream + "
                        f"{len(pay)} payload > {HOOK_BUDGET} (DoD-10)")

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

    with tempfile.TemporaryDirectory(prefix="xr-seam-patch-") as tmp:
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
        for dest, text in pay.items():
            (root / dest).parent.mkdir(parents=True, exist_ok=True)
            (root / dest).write_text(text, encoding="utf-8")
            _must(root, "add", "-N", dest)
        patch = _git(root, "diff", "--no-color", "--binary").stdout

        out.mkdir(parents=True, exist_ok=True)
        patch_path = out / f"{PATCH_ID}.patch"
        patch_path.write_text(patch, encoding="utf-8")

        # Round-trip on a pristine copy.
        _must(root, "checkout", "-q", "--", ".")
        for dest in pay:
            pth = root / dest
            if pth.exists():
                pth.unlink()
        res: dict = {
            "tool": "shield-seam-patch-roundtrip",
            "rev": rev,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "patch_sha256": _sha256(patch.encode()),
            "patch_bytes": len(patch.encode()),
            "hook_files": hooks,
            "payload_files": sorted(pay),
            "never_list": f"PASS (all files under {NEVER_ROOT}**)",
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
        for dest in pay:
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
        target = "services/network/url_loader.cc"
        anchor = "void URLLoader::ScheduleStart() {"
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
            "perturbed": f"{target}: ScheduleStart() {anchor[:30]}… + perturbed",
            "expected": "FAIL (patch is bound to the pinned bytes)",
            "observed": "FAIL" if neg.returncode != 0 else "PASS",
            "reason": (neg.stderr or neg.stdout).strip().splitlines()[:2],
        }
        res["failures"] = [] if neg.returncode != 0 else [
            "negative did not fail: patch is NOT bound to the pinned bytes"]
        return res


def main() -> int:
    ap = argparse.ArgumentParser(prog="shield_seam_roundtrip")
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
            xr_core / "patches" / "network-seams" / PATCH_ID)
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
        print(f"total files    : {len(res['hook_files']) + len(res['payload_files'])} (DoD-10 cap ≤{HOOK_BUDGET})")
        print(f"never-list     : {res['never_list']}")
        print(f"apply          : {res.get('apply')}")
        print(f"verify         : {res.get('verify')}")
        print(f"revert         : {res.get('revert')} (byte-exact: {res.get('revert_byte_exact')})")
        neg = res.get("negative", {})
        print(f"negative       : perturbed-anchor apply {neg.get('observed', 'n/a')} "
              f"(expected {neg.get('expected', 'FAIL')})")
        for f in res.get("failures", []):
            print(f"FAIL: {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
