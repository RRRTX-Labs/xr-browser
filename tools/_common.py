"""Shared helpers for XR Browser governance tools (Phase P1).

Stdlib-first. Every tool in this package:
  * exposes --help,
  * supports --json for machine-parseable output,
  * exits 0 = pass, 1 = fail, 2 = usage error (EXIT_USAGE).

Trust boundary note (Plan L5): these tools are *S0 governance tooling*.
They are header/inventory-level checkers by design (see each tool's
docstring for its exact scope); full dependency-graph resolution and
dep-graph license scanning land in P9-T9. They never overclaim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

# Repo-relative canonical locations (Plan §7.3 artifact map, P1 layout).
PLAN_FILE = "docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md"
PLAN_SHA_FILE = "docs/master-plan.sha256"
REGISTER_FILE = "docs/register/decisions.yaml"
REGISTRY_FILE = "docs/registry/features.yaml"
REGISTRY_COUNTS_FILE = "docs/registry/COUNTS.json"
THREAT_MODEL_FILE = "docs/threat-model.md"
S0_PATHS_FILE = "docs/process/s0-paths.yaml"


class ToolError(Exception):
    """Fail-closed tool error: message is the reason; exit code 1."""


def repo_root(start: str | os.PathLike | None = None) -> Path:
    """Return the git repository root containing `start` (default: cwd)."""
    cur = Path(start or Path.cwd()).resolve()
    for cand in [cur, *cur.parents]:
        if (cand / ".git").exists():
            return cand
    raise ToolError(f"no git repository found at or above {cur}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_git(cwd: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def load_yaml(path: Path) -> Any:
    """Load YAML (safe loader). Fail-closed: raises ToolError on any error."""
    try:
        import yaml  # pinned dev dependency (see tools/DEPS.md)
    except ImportError as exc:  # pragma: no cover - environment error
        raise ToolError(
            f"PyYAML not importable ({exc}); install pinned dev deps: "
            "pip install --require-hashes -r tools/requirements-dev.txt"
        ) from exc
    if not path.exists():
        raise ToolError(f"missing required file: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except Exception as exc:
        raise ToolError(f"YAML parse failure (fail-closed) in {path}: {exc}") from exc


def add_common_flags(
    parser: argparse.ArgumentParser,
    *,
    with_repo: bool = True,
) -> None:
    if with_repo:
        parser.add_argument(
            "--repo",
            default=".",
            help="repository root (default: current directory)",
        )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-parseable JSON instead of human-readable lines",
    )


def make_parser(prog: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    return parser


def emit(
    as_json: bool,
    result: dict[str, Any],
    *,
    fail_messages: list[str] | None = None,
) -> int:
    """Print result; return EXIT_PASS/EXIT_FAIL.

    fail_messages, when non-empty, are human-readable failure lines also
    included in the JSON under 'failures'.
    """
    failures = fail_messages or []
    ok = not failures
    if as_json:
        out = dict(result)
        out["status"] = "pass" if ok else "fail"
        if failures:
            out["failures"] = failures
        print(json.dumps(out, indent=2, sort_keys=False))
    else:
        if failures:
            for line in failures:
                print(f"FAIL: {line}")
        print(f"{'PASS' if ok else 'FAIL'}: {result.get('tool', 'tool')}")
    return EXIT_PASS if ok else EXIT_FAIL


def main_with_usage_guard(fn: Any) -> None:
    """Run fn(parser-args); map ToolError->1, usage errors->2."""
    try:
        rc = fn()
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(EXIT_FAIL)
    except SystemExit as exc:  # argparse usage errors
        sys.exit(EXIT_USAGE if exc.code not in (0, EXIT_USAGE) else exc.code)
    sys.exit(rc if isinstance(rc, int) else EXIT_PASS)
