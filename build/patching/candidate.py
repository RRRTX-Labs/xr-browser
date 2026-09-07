"""build/patching/candidate.py — the candidate-patch rule (P4-T1).

Split from apply.py to keep files under the 400-LOC house law.

A spike must be able to carry a patch that is NOT in the budget ledger —
otherwise a candidate would either be silently promoted or left untracked on a
branch. The rule this module enforces:

  * a patch dir under <root>/spike/patches/** is a CANDIDATE and is permitted
    only when its patchinfo.md carries `manifest-entry: NOT-YET` (i.e. it is
    honest about not being in the manifest);
  * a patch dir anywhere else (e.g. <root>/patches/branding/0002-x/) that is
    not in the manifest is a ledger violation and FAILS.

Silence is the thing being prevented: an unmanifested patch that no lint looks
at is how budget accounting dies.
"""

from __future__ import annotations

from pathlib import Path

CANDIDATE_HEADER = "manifest-entry: NOT-YET"


def lint_candidate_dirs(root: Path, manifest_ids: set[str]) -> list[str]:
    """Return a list of human-readable violations (empty == clean)."""
    fails: list[str] = []
    if not root.is_dir():
        return fails

    spike_root = root / "spike" / "patches"
    for patch_file in sorted(root.rglob("*.patch")):
        d = patch_file.parent
        try:
            rel = d.relative_to(root)
        except ValueError:
            continue
        under_spike = spike_root in d.parents or d == spike_root or (
            rel.parts[:2] == ("spike", "patches"))
        if under_spike:
            info = d / "patchinfo.md"
            if not info.is_file():
                fails.append(f"candidate {rel}: patchinfo.md missing — a "
                             f"candidate patch must declare its status")
                continue
            if CANDIDATE_HEADER not in info.read_text(encoding="utf-8"):
                fails.append(f"candidate {rel}: patchinfo.md must carry "
                             f"{CANDIDATE_HEADER!r} (a candidate is not in the "
                             f"budget ledger; say so or enter the manifest)")
            continue
        # Not under spike/: it must be accounted for in the manifest.
        in_manifest = any(part in manifest_ids for part in rel.parts) or \
            d.name in manifest_ids or patch_file.stem in manifest_ids
        if not in_manifest:
            fails.append(f"unmanifested patch dir {rel}: either add it to "
                         f"patches/manifest.yaml (budget accounting + S0 "
                         f"review) or move it under spike/patches/ with a "
                         f"{CANDIDATE_HEADER!r} header")
    return fails
