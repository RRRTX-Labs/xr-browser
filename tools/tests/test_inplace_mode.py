"""tools/inplace.py — the mode-preservation law (P13 P0-A).

The regression this pins down: `5e3d1d4` rewrote `tools/run_checks.sh` and
`tools/run_negatives.sh` with a write-new-then-replace and silently dropped
their executable bit (`git show 5e3d1d4 --raw`: `:100755 100644` on both, with
`run_checks.sh`'s content byte-identical — a mode-only diff). Nothing caught it
locally, because `bash tools/run_checks.sh` cannot see a mode; the hosted
`Governance checks` step died with exit code 126 for three commits afterwards.

This test binds the fix: a rewrite of a 0755 fixture keeps 0755, a rewrite of a
0644 fixture keeps 0644, a new file gets the explicit default rather than the
process umask, and the defect shape is shown to lose the bit (so the assertion
above is demonstrably load-bearing).
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def _import_inplace():
    sys.path.insert(0, str(TOOLS))
    try:
        import inplace  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return inplace


def test_rewrite_preserves_exec_bit(tmp_path: Path) -> None:
    inplace = _import_inplace()
    script = tmp_path / "entrypoint.sh"          # the 5e3d1d4 shape: an entry point
    script.write_text("#!/bin/sh\necho v1\n", encoding="utf-8")
    script.chmod(0o755)

    reported = inplace.rewrite_in_place(script, "#!/bin/sh\necho v2\n")

    assert stat.S_IMODE(script.stat().st_mode) == 0o755, (
        "an in-place rewrite dropped the executable bit — this is the exact "
        "defect 5e3d1d4 introduced in tools/run_checks.sh and "
        "tools/run_negatives.sh, which cost the hosted governance lane three "
        "commits of exit code 126")
    assert reported == "0o755"
    assert "echo v2" in script.read_text(encoding="utf-8")


def test_rewrite_preserves_plain_mode_and_sets_new_file_default(tmp_path: Path) -> None:
    inplace = _import_inplace()
    plain = tmp_path / "artifact.json"
    plain.write_text("{}\n", encoding="utf-8")
    plain.chmod(0o640)
    inplace.rewrite_in_place(plain, "{}\n")
    assert stat.S_IMODE(plain.stat().st_mode) == 0o640

    fresh = tmp_path / "new.txt"
    inplace.rewrite_in_place(fresh, "new\n")
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o644


def test_naive_shape_loses_the_bit(tmp_path: Path) -> None:
    """The canary: if this stops holding, the test above proves nothing."""
    inplace = _import_inplace()
    script = tmp_path / "naive.sh"
    script.write_text("#!/bin/sh\necho v1\n", encoding="utf-8")
    script.chmod(0o755)

    inplace.naive_rewrite(script, "#!/bin/sh\necho v2\n")

    assert stat.S_IMODE(script.stat().st_mode) != 0o755


def test_helper_self_test_passes_and_simulated_naive_fails() -> None:
    """`--self-test` is the CLI proof, and `--simulate-naive` proves it can fail
    (tools/negatives/p13_p0a.sh runs exactly this pair)."""
    ok = subprocess.run([sys.executable, str(TOOLS / "inplace.py"), "--self-test"],
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "0755 fixture survives an in-place rewrite" in ok.stdout

    bad = subprocess.run([sys.executable, str(TOOLS / "inplace.py"), "--self-test",
                          "--simulate-naive"], capture_output=True, text=True)
    assert bad.returncode != 0, "the self-test cannot fail — its proof is vacuous"
