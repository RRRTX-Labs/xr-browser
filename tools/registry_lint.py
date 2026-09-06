"""registry_lint.py — CI gate for the Feature Registry (Plan P1-T10).

Re-runs the derivation from the pinned Master Plan (via gen_registry) and
fails on ANY drift between plan and committed docs/registry/*:

  * docs/registry/features.yaml            rows must equal the §2.1–§2.9 parse
  * docs/registry/reserved-interfaces.yaml entries must equal the §2.10 parse
  * docs/registry/COUNTS.json              counts must equal recomputation
  * plan pin (docs/master-plan.sha256) must be present and matching

This is what makes "no feature exists outside the registry" (plan §2
preamble) machine-true: hand-editing the plan, the registry, or the
counts — in any combination — fails the build. Use
`tools/gen_registry.py --write` (after an approved plan amendment, see
docs/process/plan-amendment.md) to regenerate.

Exit codes: 0 = pass, 1 = drift/failure, 2 = usage.
"""

from __future__ import annotations

import argparse

from _common import add_common_flags, emit, main_with_usage_guard
from gen_registry import run_check


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="registry_lint.py",
        description="Fail on any drift between the pinned plan and docs/registry/*.",
    )
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        from pathlib import Path

        info, fails = run_check(Path(args.repo or ".").resolve())
        return emit(args.json, info, fail_messages=fails)

    main_with_usage_guard(run)


if __name__ == "__main__":
    main()
