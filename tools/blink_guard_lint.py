#!/usr/bin/env python3
"""tools/blink_guard_lint.py — the P12 blink-seams guard lint.

Every injected call site in a `blink_seams` patch must be behind a compile-time
guard. An unguarded hook is not a small oversight: it means the seam is compiled
into every build, including the ones where the feature is off, which is the
opposite of what a default-off flag promises. The flag would gate the CALL but
not the CODE, and code that is present can be reached.

The lint parses the patch HUNK TEXT rather than the patched tree, because the
patch is what ships and what a reviewer reads. It requires, at every injected
call site:

  * the guarded-entry pattern — `#if defined(XR_…)` … call … `#endif` — with the
    call between the two, not merely somewhere in the same file;
  * a comment naming the patch id, so a reader can find the manifest row and the
    round-trip proof without grepping;
  * no call site outside a guard.

The report line prints the counts — "hooks: N, guarded: N, unguarded: 0" —
because a lint that scanned nothing and printed PASS certifies nothing, and a
count of zero is the only way a reader can tell the difference (the zero-case
law, build/qa/_common.py).

Violations are reported as path:line so a reviewer can go to them.

Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required (pip install pyyaml)")
    sys.exit(1)

MANIFEST = "patches/manifest.yaml"
CATEGORY = "blink_seams"
# The guard macro family. A seam guard must be an XR-owned macro: reusing an
# upstream BUILDFLAG would mean the seam's presence depended on an upstream
# decision nobody here controls.
#
# "XR-owned" means the macro NAME carries an XR_ component, not that it STARTS
# with one. Chromium's convention for a compile-time feature gate is
# ENABLE_<FEATURE>, so the shipped P11 network seam is guarded by
# `#if defined(ENABLE_XR_SHIELD)` — see patches/network-seams/0200-shield-network-seam.
# A rule anchored at `^XR_` would reject that already-reviewed patch, which is
# how this regex was originally written; tools/tests/test_blink_guard_lint.py
# pins the rule against patch 0200 so the shape cannot silently narrow again.
XR_MACRO_RE = re.compile(r"\b(?:ENABLE_)?[A-Z0-9_]*XR_[A-Z0-9_]+\b")
GUARD_RE = re.compile(r"^\+\s*#if(?:def|ndef)?\b")
ENDIF_RE = re.compile(r"^\+\s*#endif")
# Upstream's own gate. `#if BUILDFLAG(IS_FOO)` is not an XR guard, so a call
# sitting inside only one of those is still compiled into builds where the
# feature is off — reported as unguarded, with the reason.
BUILDFLAG_RE = re.compile(r"\bBUILDFLAG\(")
# An injected call: an added line that reaches into the seam's own `xr::`
# namespace. It is matched ANYWHERE on the line, not at the start, because the
# two call shapes in the tree differ: P12 calls a free function
# (`blink::xr::OnDocumentStart(this);`) while P11 calls a static member, usually
# inside a condition (`if (network::xr::XrShieldGate::ShouldBlock(*req)) {`).
# An anchored pattern accepts one shape and silently counts zero hooks for the
# other, which is worse than a false alarm: "hooks: 0, PASS" certifies nothing.
# `xr::` with the scope operator is what separates a call from a payload include
# (`.../xr/xr_cosmetic_seam.h`) or a BUILD.gn source row (`"xr/xr_shield_gate.cc"`).
CALL_RE = re.compile(r"\b(?:[A-Za-z_]\w*::)*xr::(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*\s*\(")
DIFF_RE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
PATCH_COMMENT_RE = re.compile(r"patch (\d{4})")

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def _blink_seam_patches(xr_core: Path) -> list[tuple[str, Path]]:
    """(patch_id, patch_file) for every blink_seams row in the manifest."""
    man_path = xr_core / MANIFEST
    if not man_path.is_file():
        return []
    man = yaml.safe_load(man_path.read_text(encoding="utf-8"))
    out = []
    for row in man.get("patches") or []:
        if not isinstance(row, dict) or row.get("category") != CATEGORY:
            continue
        pid = row.get("id")
        d = row.get("dir")
        if not pid or not d:
            continue
        patch = xr_core / "patches" / d / f"{pid}.patch"
        if patch.is_file():
            out.append((pid, patch))
    return out


def scan_patch(patch: Path) -> dict[str, object]:
    """Walk a patch's hunks, tracking guard state per added line."""
    hooks = 0
    guarded = 0
    violations: list[str] = []
    current: str | None = None
    new_lineno = 0
    guard_depth = 0
    guard_id: str | None = None
    # Accumulated across the WHOLE patch. Tracking only the last guard seen
    # reports `[]` whenever the patch's final file carries no guard — which is
    # the normal shape, since payload files come last — and an empty
    # `guard_macros` on a patch that is in fact guarded reads like "no guard
    # macro found at all".
    guard_macros: set[str] = set()
    # The nearest preceding comment naming a patch id, per file. A hook with no
    # such comment is a violation: a reader must be able to find the manifest
    # row and the round-trip proof without grepping the tree.
    last_comment_line = -1
    seen_ids: set[str] = set()
    foreign_guard = False
    spanned = 0

    for raw in patch.read_text(encoding="utf-8").splitlines():
        m = DIFF_RE.match(raw)
        if m:
            current = m.group(1)
            guard_depth = 0
            guard_id = None
            last_comment_line = -1
            continue
        h = HUNK_RE.match(raw)
        if h:
            new_lineno = int(h.group(1))
            # Guard depth is HUNK-LOCAL. A leaked depth across hunks is a false
            # PASS (a call reported guarded by an `#if` in some other hunk), and
            # a false pass is the failure this lint exists to prevent, so the
            # conservative reading wins: reset, and complain if an `#endif`
            # closes a guard this hunk never opened.
            if guard_depth:
                spanned += 1
            guard_depth = 0
            foreign_guard = False
            continue
        if current is None or not raw.startswith("+") or raw.startswith("+++"):
            continue
        body = raw[1:]
        new_lineno += 1
        stripped = body.lstrip()

        cm = PATCH_COMMENT_RE.search(body)
        if cm and stripped.startswith(("//", "#", "/*", "*")):
            last_comment_line = new_lineno
            seen_ids.add(cm.group(1))

        if GUARD_RE.match(raw):
            # Only an XR-owned macro opens a guard we will credit.
            gm = XR_MACRO_RE.search(body)
            if gm and not BUILDFLAG_RE.search(body):
                guard_depth += 1
                guard_id = gm.group(0)
                guard_macros.add(guard_id)
            else:
                foreign_guard = True
            continue
        if ENDIF_RE.match(raw):
            if guard_depth == 0:
                spanned += 1
            else:
                guard_depth -= 1
            continue
        # Comments and includes are not call sites: they name the seam without
        # reaching it, and counting them would inflate `hooks`.
        if stripped.startswith(("//", "/*", "*", "#include")):
            continue
        if CALL_RE.search(body):
            hooks += 1
            where = f"{current}:{new_lineno}"
            if guard_depth == 0:
                why = ("the enclosing `#if` is an upstream BUILDFLAG, not an "
                       "XR-owned macro, so the seam still compiles where the "
                       "feature is off"
                       if foreign_guard else
                       "the call site must sit inside "
                       "`#if defined(ENABLE_XR_…)` / `#endif`")
                violations.append(
                    f"{where}: unguarded seam call — {why}")
                continue
            if last_comment_line < 0:
                violations.append(
                    f"{where}: seam call has no comment naming the patch id — "
                    f"a reader must be able to reach the manifest row and the "
                    f"round-trip proof without grepping")
                continue
            guarded += 1
    if guard_depth:
        spanned += 1
    if spanned:
        violations.append(
            f"{current}: a guard spans a hunk boundary ({spanned} "
            f"unbalanced `#if`/`#endif` across hunks) — the lint reasons "
            f"hunk-locally, so it cannot prove those call sites are guarded; "
            f"keep each guard inside one hunk")
    return {"hooks": hooks, "guarded": guarded, "violations": violations,
            "patch_ids": sorted(seen_ids), "hunk_spanned": spanned,
            "guard_macros": sorted(guard_macros)}


def check(repo: Path, xr_core: Path) -> tuple[list[str], int, int]:
    fails: list[str] = []
    patches = _blink_seam_patches(xr_core)
    if not patches:
        # Zero blink_seams patches is NOT a failure: the category may be unused.
        # But the lint must say so loudly, because "0 hooks, PASS" and "scanned
        # nothing, PASS" are different claims and only the counts tell them
        # apart.
        print("NOTE: no blink_seams patches in the manifest — nothing to lint")
        return fails, 0, 0
    total_hooks = 0
    total_guarded = 0
    for pid, patch in patches:
        res = scan_patch(patch)
        total_hooks += int(res["hooks"])
        total_guarded += int(res["guarded"])
        for v in res["violations"]:
            fails.append(f"{pid}: {v}")
        if int(res["hooks"]) == 0:
            fails.append(f"{pid}: zero seam calls in the patch — a blink_seams "
                         f"patch with no call site hooks nothing, so either "
                         f"the category is wrong or the seam is missing")
        if pid.split("-", 1)[0] not in res["patch_ids"]:
            fails.append(f"{pid}: no comment in the patch names its own id "
                         f"({pid.split('-', 1)[0]}) — the guard pattern "
                         f"requires the patch id at the call site")
    return fails, total_hooks, total_guarded


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="blink-guard-lint",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--xr-core", default=None)
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    xr_core = (Path(a.xr_core).resolve() if a.xr_core
               else (repo / "../xr-core").resolve())
    fails, hooks, guarded = check(repo, xr_core)
    for f in fails:
        print(f"FAIL: {f}")
    unguarded = hooks - guarded
    if fails:
        print(f"FAIL: blink_guard_lint (hooks: {hooks}, guarded: {guarded}, "
              f"unguarded: {unguarded}; {len(fails)} finding(s))")
        return EXIT_FAIL
    print(f"PASS: blink_guard_lint (hooks: {hooks}, guarded: {guarded}, "
          f"unguarded: 0)")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
