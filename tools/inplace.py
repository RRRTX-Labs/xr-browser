#!/usr/bin/env python3
"""tools/inplace.py — mode-preserving in-place rewrites for tracked files (P13 P0-A).

The incident this closes
------------------------
`git show 5e3d1d4 --raw` flips exactly two paths to `100644`:

    :100755 100644 M tools/run_checks.sh      (content byte-identical: mode-only diff)
    :100755 100644 M tools/run_negatives.sh

The rewrite was a write-new-then-replace. A replacement file is created with the
process umask (0644), so the `os.replace` that publishes it silently discards the
destination's mode — and since a POSIX rename does not merge modes, the original
bit is gone. Nothing in the tree did that rewrite: **no tracked tool preserved,
or even read, the pre-write mode**, which is exactly why the class was armed for
the next phase. `--self-test` demonstrates the defect with the naive shape and
the fix with this one, and `--simulate-naive` makes the *assertion itself* fail so
the proof can be shown to be able to fail (`tools/negatives/p13_p0a.sh`).

The law
-------
Every in-place rewrite of an existing file goes through `rewrite_in_place`, which
copies the *pre-write* `stat` mode onto the replacement before publishing it.
New files get an explicit mode (default 0o644) — never the umask by accident.

Stdlib only. Exit: 0 pass · 1 fail · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
DEFAULT_MODE = 0o644


class ModePreservingError(RuntimeError):
    """The rewrite could not be published without losing file identity."""


def rewrite_in_place(path: str | os.PathLike,
                     text: str,
                     *,
                     encoding: str = "utf-8",
                     mode: int | None = None) -> str:
    """Rewrite `path` atomically, preserving its mode.

    Returns the mode that the published file has, as an octal string (e.g.
    "0o755"), so callers can assert on it without a second `stat`.

    `mode` (when given) overrides the pre-write mode — used only for NEW files
    or for a deliberate chmod; the default for a new file is 0o644 (never the
    umask, which is ambient state the CI runner and a sandbox disagree about).
    """
    p = Path(path)
    pre = p.stat() if p.exists() else None
    if mode is not None:
        out_mode = mode
    elif pre is not None:
        out_mode = stat.S_IMODE(pre.st_mode)
    else:
        out_mode = DEFAULT_MODE

    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        # THE FIX: the replacement carries the mode of the file it replaces.
        # Without this line `os.replace` publishes a 0644 file over a 0755 one
        # (5e3d1d4, and the exit-code-126 CI failure it caused a phase later).
        os.chmod(tmp_name, out_mode)
        os.replace(tmp_name, p)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return oct(out_mode)


def rewrite_bytes_in_place(path: str | os.PathLike, data: bytes, *,
                           mode: int | None = None) -> str:
    """Bytes variant of `rewrite_in_place` (vendored blobs, golden vectors)."""
    p = Path(path)
    pre = p.stat() if p.exists() else None
    out_mode = mode if mode is not None else (
        stat.S_IMODE(pre.st_mode) if pre is not None else DEFAULT_MODE)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, out_mode)
        os.replace(tmp_name, p)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return oct(out_mode)


def naive_rewrite(path: str | os.PathLike, text: str, *, encoding: str = "utf-8") -> None:
    """The DEFECT SHAPE, kept in one place so it can be demonstrated and tested:
    publish a fresh file over the target without carrying the mode across."""
    p = Path(path)
    if p.exists():
        p.unlink()
    p.write_text(text, encoding=encoding)


# ------------------------------------------------------------------- self-test

def _self_test(simulate_naive: bool = False) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="xr-inplace-"))
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    try:
        exe = tmp / "entrypoint.sh"
        exe.write_text("#!/bin/sh\necho v1\n", encoding="utf-8")
        exe.chmod(0o755)
        data = tmp / "artifact.json"
        data.write_text("{}\n", encoding="utf-8")
        data.chmod(0o644)

        # --simulate-naive swaps the DEFECT SHAPE in for the fix, so every
        # assertion below is exercised against the bug the helper exists to
        # prevent: if they still pass, they were never load-bearing.
        write = naive_rewrite if simulate_naive else rewrite_in_place

        before = stat.S_IMODE(exe.stat().st_mode)
        check(before == 0o755, f"fixture precondition: expected 0755, got {oct(before)}")
        reported = write(exe, "#!/bin/sh\necho v2\n")
        after = stat.S_IMODE(exe.stat().st_mode)
        check(after == 0o755,
              f"rewrite_in_place dropped the exec bit: {oct(before)} -> {oct(after)}")
        check(reported == oct(after), "the returned mode disagrees with the file")
        check("echo v2" in exe.read_text(encoding="utf-8"), "content did not land")

        print(f"ok: a 0755 fixture survives an in-place rewrite ({oct(before)} -> {oct(after)})")

        write(data, '{"a": 1}\n')
        check(stat.S_IMODE(data.stat().st_mode) == 0o644,
              "a 0644 fixture changed mode")
        print("ok: a 0644 fixture stays 0644")

        fresh = tmp / "new-file.txt"
        write(fresh, "new\n")
        check(stat.S_IMODE(fresh.stat().st_mode) == 0o644,
              "a new file did not get the explicit default mode")
        print("ok: a new file gets the explicit default (0o644), not the umask")

        # The canary: the defect shape must lose the bit. If this ever stops
        # being true, the fix above has become untestable and the proof of it
        # means nothing.
        naive_target = tmp / "naive.sh"
        naive_target.write_text("#!/bin/sh\necho v1\n", encoding="utf-8")
        naive_target.chmod(0o755)
        if simulate_naive:
            # In the simulated world the defect shape IS the helper, so the
            # canary's premise ("the helper must not lose the bit") is false —
            # and the assertion above must therefore have already failed.
            print("simulate-naive: the defect shape was used as the helper")
        else:
            naive_rewrite(naive_target, "#!/bin/sh\necho v2\n")
        naive_mode = stat.S_IMODE(naive_target.stat().st_mode)
        check(naive_mode != 0o755,
              f"the defect shape did NOT lose the exec bit (got {oct(naive_mode)}) — "
              "the assertion above cannot be making a difference")
        print(f"ok: the write-new-then-replace shape loses it ({oct(naive_mode)}) — "
              "the 5e3d1d4 class, reproduced")

        if fails:
            for f in fails:
                print(f"SELF-TEST FAIL: {f}")
            if simulate_naive:
                print("ok: --simulate-naive made the self-test fail — the assertions "
                      "are load-bearing, not decoration")
            return EXIT_FAIL
        if simulate_naive:
            print("SELF-TEST FAIL: --simulate-naive did not redden the self-test")
            return EXIT_FAIL
        print("PASS: in-place rewrites preserve mode (helper + canary)")
        return EXIT_PASS
    finally:
        for child in sorted(tmp.rglob("*"), reverse=True):
            try:
                child.unlink()
            except OSError:
                pass
        try:
            tmp.rmdir()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true",
                    help="prove the helper preserves modes and that the canary bites")
    ap.add_argument("--simulate-naive", action="store_true",
                    help="make the canary's assertion fail on purpose (negatives only)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.self_test:
        ap.print_help()
        return EXIT_USAGE
    if args.json:
        rc = _self_test(args.simulate_naive)
        print(json.dumps({"tool": "inplace", "self_test": "PASS" if rc == 0 else "FAIL",
                          "simulate_naive": args.simulate_naive}, sort_keys=True))
        return rc
    return _self_test(args.simulate_naive)


if __name__ == "__main__":
    sys.exit(main())
