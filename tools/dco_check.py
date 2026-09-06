"""dco_check.py — Developer Certificate of Origin gate (Plan P1-T13).

Both repos are MPL-2.0 + DCO (plan P1-T1, ADR-0001). This check
implements the "DCO bot blocks unsigned PR" DoD locally and in CI:

For every commit in the range:
  * at least one `Signed-off-by: Name <email>` trailer is present, and
  * the signoff email matches the commit's committer email (the DCO
    signoff certifies the contribution; it must come from the same
    identity that committed — email compared case-insensitively).

Range semantics:
  * default: full history (root..HEAD),
  * `--range <rev-range>`: a git rev range (CI passes the PR range,
    e.g. `origin/main..HEAD`).

Exit codes: 0 = pass, 1 = fail, 2 = usage.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from _common import (
    ToolError,
    add_common_flags,
    emit,
    main_with_usage_guard,
    repo_root,
    run_git,
)

SIGNOFF_RE = re.compile(r"^Signed-off-by:\s*(?P<name>.+?)\s*<(?P<email>[^>]+)>\s*$", re.MULTILINE)


def run(args: argparse.Namespace) -> int:
    root = repo_root(args.repo)
    fails: list[str] = []
    rng = [args.range] if args.range else ["HEAD"]
    rc, out, err = run_git(root, "log", "--format=%H%x1f%ce%x1f%s", *rng)
    if rc != 0:
        raise ToolError(f"git log failed: {err.strip() or out.strip()}")

    checked = 0
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, committer_email, subject = line.split("\x1f", 2)
        rc2, body, err2 = run_git(root, "log", "-1", "--format=%B%x1f%ae", sha)
        if rc2 != 0:
            raise ToolError(f"git log -1 failed for {sha[:12]}: {err2.strip()}")
        msg, author_email = body.rstrip("\n").rsplit("\x1f", 1)
        checked += 1
        signoffs = SIGNOFF_RE.findall(msg)
        if not signoffs:
            fails.append(f"{sha[:12]} ({subject}): missing Signed-off-by trailer")
            continue
        for _name, email in signoffs:
            if email.lower() == committer_email.lower():
                break
        else:
            fails.append(
                f"{sha[:12]} ({subject}): signoff email {[e for _n, e in signoffs]} does not match "
                f"committer email {committer_email!r}"
            )

    info = {
        "tool": "dco_check",
        "range": args.range or "all history",
        "commits_checked": checked,
    }
    return emit(args.json, info, fail_messages=fails)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dco_check.py",
        description="Verify every commit in range carries a matching DCO signoff.",
    )
    parser.add_argument("--range", default=None, help="git rev range (default: full history)")
    add_common_flags(parser)
    args = parser.parse_args()
    main_with_usage_guard(lambda: run(args))


if __name__ == "__main__":
    main()
