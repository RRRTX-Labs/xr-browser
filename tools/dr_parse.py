"""dr_parse.py — Decision Register validator (Plan P1-T9, ADR-0002).

Two jobs:
1. Schema validation of docs/register/decisions.yaml:
   * all of DR-01..DR-30 present exactly once,
   * required fields + status enum {RATIFIED, OPEN, GATE-PENDING,
     MONITORED},
   * LG refs well-formed, phase anchors within P1..P39,
   * plan_sha256 consistent with docs/master-plan.sha256 when that file
     exists (plan pin lands in P1-T11; fail-closed on mismatch, skip
     with a note when not yet present).
2. Register-change protection: every commit touching
   docs/register/decisions.yaml must carry the trailer
   `Register-Change: ADR-<nnnn>` (ADR-0002 §2). CI runs this over the PR
   range; --check-trailers without --range checks the full history.

Exit codes: 0 = pass, 1 = fail (any validation error), 2 = usage.
Scope honesty (L5): this tool validates the register's *form* and its
*change discipline*; it does not judge the engineering content of a
decision (that is the ADR + human deciders, ADR-0002 §4).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from _common import (
    PLAN_SHA_FILE,
    REGISTER_FILE,
    ToolError,
    add_common_flags,
    emit,
    load_yaml,
    main_with_usage_guard,
    repo_root,
    run_git,
    sha256_file,
)

VALID_STATUS = {"RATIFIED", "OPEN", "GATE-PENDING", "MONITORED"}
EXPECTED_IDS = [f"DR-{n:02d}" for n in range(1, 31)]
REQUIRED_FIELDS = (
    "id",
    "title",
    "status",
    "rationale",
    "linked_lg",
    "reopen_condition",
    "phase_anchor",
)
LG_RE = re.compile(r"^LG-\d{1,2}$")
PHASE_RE = re.compile(r"P(\d{1,2})")
TRAILER_RE = re.compile(r"^Register-Change:\s*ADR-\d{4}\s*$", re.MULTILINE)


def _check_entry(i: int, entry: Any, fails: list[str]) -> str | None:
    if not isinstance(entry, dict):
        fails.append(f"decisions[{i}]: not a mapping")
        return None
    for field in REQUIRED_FIELDS:
        if field not in entry:
            fails.append(f"decisions[{i}]: missing field {field!r}")
    if "id" not in entry:
        return None
    drid = entry["id"]
    if not isinstance(drid, str) or not re.fullmatch(r"DR-\d{2}", drid):
        fails.append(f"decisions[{i}]: bad id {drid!r} (want DR-NN)")
        return None
    for field in ("title", "rationale", "reopen_condition", "phase_anchor"):
        val = entry.get(field)
        if not isinstance(val, str) or not val.strip():
            fails.append(f"{drid}: field {field!r} must be a non-empty string")
    status = entry.get("status")
    if status not in VALID_STATUS:
        fails.append(f"{drid}: status {status!r} not in {sorted(VALID_STATUS)}")
    lg = entry.get("linked_lg")
    if not isinstance(lg, list) or any(not isinstance(x, str) or not LG_RE.match(x) for x in lg):
        fails.append(f"{drid}: linked_lg must be a list of 'LG-n' strings (got {lg!r})")
    anchor = entry.get("phase_anchor")
    if isinstance(anchor, str) and anchor.strip():
        phases = PHASE_RE.findall(anchor)
        if not phases or any(not (1 <= int(p) <= 39) for p in phases):
            fails.append(f"{drid}: phase_anchor {anchor!r} has no valid P1..P39 phase token")
    return drid


def validate_register(root: Path) -> tuple[dict[str, Any], list[str]]:
    fails: list[str] = []
    data = load_yaml(root / REGISTER_FILE)
    if not isinstance(data, dict):
        raise ToolError(f"{REGISTER_FILE}: top level must be a mapping")

    sha_field = data.get("plan_sha256")
    if not isinstance(sha_field, str) or not re.fullmatch(r"[0-9a-f]{64}", sha_field):
        fails.append("register: plan_sha256 must be a 64-hex-digit string")

    plan_pin = "skipped (master-plan.sha256 not present yet)"
    sha_file = root / PLAN_SHA_FILE
    if sha_file.exists():
        try:
            line = sha_file.read_text(encoding="utf-8").strip().splitlines()[0]
            pinned = line.split()[0]
            if re.fullmatch(r"[0-9a-f]{64}", pinned) and sha_field and pinned != sha_field:
                fails.append(f"register: plan_sha256 {sha_field} != pinned {pinned}")
            else:
                plan_pin = "verified against master-plan.sha256"
        except (IndexError, UnicodeDecodeError) as exc:
            fails.append(f"register: cannot parse {PLAN_SHA_FILE}: {exc}")
    elif sha_field:
        plan_pin = "pin file not present yet (P1-T11) — hash field recorded"

    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        raise ToolError(f"{REGISTER_FILE}: 'decisions' must be a list")

    ids: list[str | None] = []
    for i, entry in enumerate(decisions):
        ids.append(_check_entry(i, entry, fails))

    id_set = [x for x in ids if x]
    seen: set[str] = set()
    for drid in id_set:
        if drid in seen:
            fails.append(f"duplicate id {drid}")
        seen.add(drid)
    for expected in EXPECTED_IDS:
        if expected not in seen:
            fails.append(f"missing DR id {expected}")
    for drid in id_set:
        if drid not in EXPECTED_IDS:
            fails.append(f"unexpected DR id {drid} (expected DR-01..DR-30)")

    statuses: dict[str, int] = {}
    for entry in decisions:
        if isinstance(entry, dict) and isinstance(entry.get("status"), str):
            statuses[entry["status"]] = statuses.get(entry["status"], 0) + 1

    info = {
        "register": str(root / REGISTER_FILE),
        "entries": len(decisions),
        "expected": len(EXPECTED_IDS),
        "statuses": statuses,
        "plan_pin": plan_pin,
    }
    return info, fails


def check_trailers(root: Path, rng: str | None) -> tuple[dict[str, Any], list[str]]:
    fails: list[str] = []
    revs = [rng] if rng else ["HEAD"]
    rc, out, err = run_git(root, "log", "--format=%H%x1f%s", *revs, "--", REGISTER_FILE)
    if rc != 0:
        raise ToolError(f"git log failed: {err.strip() or out.strip()}")
    checked = 0
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, subject = line.split("\x1f", 1)
        rc2, msg, err2 = run_git(root, "log", "-1", "--format=%B", sha)
        if rc2 != 0:
            raise ToolError(f"git log -1 failed for {sha[:12]}: {err2.strip()}")
        checked += 1
        if not TRAILER_RE.search(msg):
            fails.append(
                f"commit {sha[:12]} ({subject}) touches {REGISTER_FILE} without a "
                "'Register-Change: ADR-<nnnn>' trailer (ADR-0002 §2)"
            )
    info = {"range": rng or "all history", "commits_touching_register": checked}
    return info, fails


def run(args: argparse.Namespace) -> int:
    root = repo_root(args.repo)
    fails: list[str] = []
    info: dict[str, Any] = {"tool": "dr_parse"}

    if args.check_trailers:
        tinfo, tfails = check_trailers(root, args.range)
        info["trailers"] = tinfo
        fails.extend(tfails)
    else:
        rinfo, rfails = validate_register(root)
        info.update(rinfo)
        fails.extend(rfails)

    return emit(args.json, info, fail_messages=fails)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dr_parse.py",
        description="Validate the Decision Register (schema + Register-Change trailers).",
    )
    parser.add_argument(
        "--check-trailers",
        action="store_true",
        help="verify commits touching decisions.yaml carry Register-Change: ADR-<nnnn>",
    )
    parser.add_argument(
        "--range",
        default=None,
        help="git range for --check-trailers (default: full history)",
    )
    add_common_flags(parser)
    args = parser.parse_args()
    main_with_usage_guard(lambda: run(args))


if __name__ == "__main__":
    main()
