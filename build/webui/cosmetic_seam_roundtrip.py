"""cosmetic_seam_roundtrip.py — the P12 (T1) code-level proof: the blink_seams
patch 0300 round-trips at the pin, and every symbol it hooks really exists.

Same contract as build/webui/shield_seam_roundtrip.py (P11) and
build/webui/patch_roundtrip.py (P7): no remembered contents, no fixtures.

  1. Fetches the exact upstream files the patch modifies at the DEPS
     chromium_rev through build/upstream/fetch.py (the only network choke
     point). A fetch failure is BLOCKED-NET, never simulated.
  2. Assembles a throwaway git checkout of those files at their Chromium paths,
     commits it ("pre" state, every file hashed).
  3. Applies the guarded hook transforms + materializes the payload sources from
     the patch dir, then `git diff`s: that diff IS the manifest patch.
  4. Round-trip on a pristine copy: `git apply --check` -> apply -> every
     expected marker present -> `git apply -R` -> byte-exact compare of every
     file against the pre-state hashes, and no residual files.
  5. Negative: perturb a pinned anchor line and assert the patch then FAILS to
     apply (the patch is bound to the pin, so upstream drift is caught).
  6. Never-list: refuses any target outside third_party/blink/renderer/core/**
     (§12.7 puts blink/** on the never-list; see the manifest row's note).
  7. Budget: total files <= the blink_seams category cap.

WHY THIS TOOL EXISTS, BEYOND THE ROUND-TRIP.

Because step 3 re-derives the patch from the PINNED bytes and refuses to
proceed when an anchor is absent or ambiguous, it is also the only check in the
tree that a hooked symbol EXISTS at the pin. During P12 the first draft of patch
0300 hooked `Document::ParseRootElementBeforeChildren` — a function that is not
in Chromium 152 at all. A hand-written patch reports nothing about that; the
lint sees a syntactically fine hunk and passes it. This tool reported
"anchor not found (upstream drift)" and the hook moved to
`Document::WillInsertBody` (document.cc, real at the pin). Keep it that way:
never hand-write a hunk header, never hand-copy an anchor out of memory.

WHAT THIS TOOL DOES *NOT* PROVE.

gn and ninja are absent from the environment it runs in, so it does not run gn
and does not compile the payload. It proves the patch applies and reverts
byte-exactly at the pin against real upstream files; it does NOT prove the
payload builds, and no page-level behaviour is claimed anywhere in P12 — the
page assertions are HG-31 and run in the nightly build.

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

# 77 is this repo's skip code (tools/scheduled_lane_check.py,
# build/qa/drill/drill_run.sh both use it). A fetch failure is an ENVIRONMENT
# gap, not a failed check, so it must be visible as a SKIP and never as a pass:
# the guard lint runs unconditionally in the same gate section, so a SKIP here
# still leaves a real check of the seam's guard discipline behind it.
EXIT_BLOCKED = 77

PATCH_ID = "0300-cosmetic-document-start"
NEVER_ROOT = "third_party/blink/renderer/core/"
# The manifest's blink_seams category cap, which is also the brief's "<=25
# files" budget for the seam. Asserted below against the real file count.
HOOK_BUDGET = 25
PAYLOAD_PREFIX = "third_party/blink/renderer/core/xr/"

CORE_GN = "third_party/blink/renderer/core/BUILD.gn"
DOCUMENT_CC = "third_party/blink/renderer/core/dom/document.cc"

# The guarded call site. blink_guard_lint.py (xr-browser) requires all three
# pieces — the `#if defined(ENABLE_XR_…)` guard, a comment naming the patch id,
# and the call between them — so the text here and that lint are coupled by
# design; changing one without the other reddens the gate.
HOOK = """#if defined(ENABLE_XR_COSMETIC)
  // P12 cosmetic seam (patch 0300): install the cosmetic key set for this
  // frame's own scope before the body exists.
  //
  // Fail-open: OnDocumentStart returns void and cannot fail the load. Every
  // refusal inside it — no blob, digest mismatch, malformed ABPF, oversized key
  // set, any parse failure — installs nothing and the page renders unstyled.
  // Refusing to hide an ad must never refuse to render a page.
  blink::xr::OnDocumentStart(this);
#endif  // ENABLE_XR_COSMETIC"""

# Inserted inside component("core"), after its deps list closes. `defines`
# belongs to the target, so the `#if` at the document.cc call site compiles;
# the flag gates the CODE, not merely the call.
GN_BLOCK = """
  # P12 cosmetic seam (patch 0300): the document-start hook lives in this
  # target's document.cc, so the guard macro has to be defined HERE for the
  # `#if defined(ENABLE_XR_COSMETIC)` call site to compile at all. Default off
  # (build/gn/argsets/flags.yaml: xr_shield_cosmetic_v1, kind xr, false), so the
  # off state neither defines the macro nor links the payload.
  if (xr_shield_cosmetic_v1) {
    defines = [ "ENABLE_XR_COSMETIC=1" ]
    deps += [ "//third_party/blink/renderer/core/xr:xr_cosmetic_seam" ]
  }"""

# Upstream hook transforms. Each `anchor` MUST occur exactly once in the pinned
# file (asserted); `insert_after` appends the text on a new line after it.
TARGETS: list[dict] = [
    {"path": CORE_GN, "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '    "//ui/strings",\n  ]',
         "text": GN_BLOCK}]},
    {"path": DOCUMENT_CC, "fetch": True, "ops": [
        {"kind": "insert_after",
         "anchor": '#include "third_party/blink/renderer/core/dom/document.h"',
         "text": '#include "third_party/blink/renderer/core/xr/'
                 'xr_cosmetic_seam.h"  // XR cosmetic seam (patch 0300)'},
        {"kind": "insert_after",
         "anchor": "void Document::WillInsertBody() {",
         "text": HOOK}]},
]

# Post-apply markers: proof the patch did the job, not merely that it applied.
MARKERS = [
    (CORE_GN, 'defines = [ "ENABLE_XR_COSMETIC=1" ]'),
    (CORE_GN, '"//third_party/blink/renderer/core/xr:xr_cosmetic_seam"'),
    (DOCUMENT_CC, "#if defined(ENABLE_XR_COSMETIC)"),
    (DOCUMENT_CC, "blink::xr::OnDocumentStart(this);"),
    (DOCUMENT_CC, "#endif  // ENABLE_XR_COSMETIC"),
]

# The negative perturbs this anchor: it is the call site, so breaking it is the
# drift that matters most (a vanished hook is a silent loss of the feature).
NEGATIVE = {"path": DOCUMENT_CC, "anchor": "void Document::WillInsertBody() {"}


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
    base = xr_core / "patches" / "blink-seams" / PATCH_ID / "payload"
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
            # This is the check that caught the invented function. "upstream
            # drift" is one possible cause; the other, and the one that actually
            # happened in P12, is an anchor that was never upstream to begin
            # with. Both must stop the tool rather than be guessed around.
            raise ToolError("anchor not found at the pin (upstream drift, or "
                            "the symbol does not exist — verify before "
                            f"hand-editing): {op['anchor'][:70]!r}")
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
        raise ToolError(f"never-list refusal (must stay {NEVER_ROOT}**): "
                        + "; ".join(refusals))
    if len(hooks) + len(pay) > HOOK_BUDGET:
        raise ToolError(f"hook budget blown: {len(hooks)} upstream + "
                        f"{len(pay)} payload > {HOOK_BUDGET} (blink_seams cap)")

    from fetch import FetchError, GitilesFetchSource  # the choke point
    src = GitilesFetchSource()
    fetched: dict[str, str] = {}
    for t in TARGETS:
        if not t["fetch"]:
            continue
        try:
            fetched[t["path"]] = src.file_text(rev, t["path"])
        except FetchError as exc:
            raise ToolError(f"BLOCKED-NET: cannot fetch {t['path']} at {rev}: "
                            f"{exc}")
        for op in t["ops"]:
            if fetched[t["path"]].count(op["anchor"]) != 1:
                raise ToolError(f"anchor not unique in {t['path']}: "
                                f"{op['anchor'][:70]!r}")

    with tempfile.TemporaryDirectory(prefix="xr-cosmetic-patch-") as tmp:
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

        for t in TARGETS:
            if not t["fetch"]:
                continue
            (root / t["path"]).write_text(
                apply_ops(fetched[t["path"]], t["ops"]), encoding="utf-8")
        for dest, text in pay.items():
            (root / dest).parent.mkdir(parents=True, exist_ok=True)
            (root / dest).write_text(text, encoding="utf-8")
            _must(root, "add", "-N", dest)
        patch = _git(root, "diff", "--no-color", "--binary").stdout

        out.mkdir(parents=True, exist_ok=True)
        patch_path = out / f"{PATCH_ID}.patch"
        patch_path.write_text(patch, encoding="utf-8")

        _must(root, "checkout", "-q", "--", ".")
        for dest in pay:
            pth = root / dest
            if pth.exists():
                pth.unlink()
        res: dict = {
            "tool": "cosmetic-seam-patch-roundtrip",
            "rev": rev,
            "generated_at": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "patch_sha256": _sha256(patch.encode()),
            "patch_bytes": len(patch.encode()),
            "hook_files": hooks,
            "payload_files": sorted(pay),
            "never_list": f"PASS (all files under {NEVER_ROOT}**)",
            "budget": f"{len(hooks) + len(pay)}/{HOOK_BUDGET}",
            "source": "real-fetch",
            # Stated in the artifact, not only in prose: nothing here ran gn.
            "compiled": "NOT-RUN (gn/ninja absent — no Chromium build claimed)",
        }

        check = _git(root, "apply", "--check", str(patch_path))
        if check.returncode != 0:
            res["apply"] = "FAIL"
            res["failures"] = [
                f"git apply --check refused: "
                f"{(check.stderr or check.stdout).strip()}"]
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
        drift = {k: (v, post.get(k)) for k, v in pre.items()
                 if post.get(k) != v}
        leftover = sorted(set(post) - set(pre))
        res["revert"] = "PASS" if not drift and not leftover else "FAIL"
        res["revert_byte_exact"] = not drift and not leftover
        if drift or leftover:
            res["failures"] = ([f"revert drift: {k}" for k in drift]
                               + [f"residual file: {f}" for f in leftover])
            return res

        # Negative: perturb the call-site anchor -> the patch must fail to apply.
        target, anchor = NEGATIVE["path"], NEGATIVE["anchor"]
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
            "test": "perturb the pinned call-site anchor, then git apply --check",
            "perturbed": f"{target}: {anchor} + perturbed",
            "expected": "FAIL (patch is bound to the pinned bytes)",
            "observed": "FAIL" if neg.returncode != 0 else "PASS",
            "reason": (neg.stderr or neg.stdout).strip().splitlines()[:2],
        }
        res["failures"] = [] if neg.returncode != 0 else [
            "negative did not fail: patch is NOT bound to the pinned bytes"]
        return res


def main() -> int:
    ap = argparse.ArgumentParser(prog="cosmetic_seam_roundtrip")
    ap.add_argument("--rev", help="40-char chromium rev (default: DEPS)")
    ap.add_argument("--xr-core", default="../xr-core")
    ap.add_argument("--out", default="",
                    help="artifact dir (default: the manifest patch dir)")
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
            xr_core / "patches" / "blink-seams" / PATCH_ID)
        if not out.is_absolute():
            out = root / out
        res = roundtrip(rev=rev, xr_core=xr_core, out=out)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if str(exc).startswith("BLOCKED-NET:"):
            return EXIT_BLOCKED
        return 1

    ok = not res.get("failures")
    res["status"] = "pass" if ok else "fail"
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"rev            : {res['rev']}")
        print(f"patch          : {res['patch_bytes']} B  "
              f"sha256 {res['patch_sha256'][:16]}…")
        print(f"hook files ({len(res['hook_files'])}): "
              + ", ".join(res["hook_files"]))
        print(f"payload files ({len(res['payload_files'])}): "
              + ", ".join(res["payload_files"]))
        print(f"total files    : {len(res['hook_files']) + len(res['payload_files'])}"
              f" (blink_seams cap ≤{HOOK_BUDGET})")
        print(f"never-list     : {res['never_list']}")
        print(f"compiled       : {res['compiled']}")
        print(f"apply          : {res.get('apply')}")
        print(f"verify         : {res.get('verify')}")
        print(f"revert         : {res.get('revert')} "
              f"(byte-exact: {res.get('revert_byte_exact')})")
        neg = res.get("negative", {})
        print(f"negative       : perturbed-anchor apply {neg.get('observed', 'n/a')} "
              f"(expected {neg.get('expected')})")
        for f in res.get("failures", []):
            print(f"FAIL: {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
