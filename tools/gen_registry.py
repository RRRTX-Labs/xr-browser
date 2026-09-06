"""gen_registry.py — derive the Feature Registry from the pinned Master Plan.

The plan declares (§2 preamble, its "How to use" line): "Section 2 is the
feature registry: no feature exists outside it." This tool makes that
machine-true: it parses the markdown tables of the pinned plan
(§2.1–§2.9) and the reserved-interface list of §2.10, and writes:

  docs/registry/features.yaml            one entry per §2 table row
  docs/registry/reserved-interfaces.yaml §2.10 reserved interfaces
  docs/registry/COUNTS.json              section/status/criticality counts

The committed files are *generated artifacts*: hand-edits are drift. CI
runs `--check` (regenerate in memory, compare, fail on any difference);
`--write` is what a maintainer runs after an approved plan amendment.

Field policy (lossless + machine-checkable):
  * raw_* fields keep the plan's text verbatim (no editorializing),
  * derived fields (id, decision_class, status, tokens) are computed,
  * "—" means "not specified in the plan" and is stored as null.

Exit codes: 0 = pass/ok, 1 = drift or parse failure, 2 = usage.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import (
    PLAN_FILE,
    PLAN_SHA_FILE,
    ToolError,
    add_common_flags,
    main_with_usage_guard,
    sha256_file,
)

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML not importable ({exc}); install pinned dev deps") from exc

FEATURES_FILE = "docs/registry/features.yaml"
RESERVED_FILE = "docs/registry/reserved-interfaces.yaml"
COUNTS_FILE = "docs/registry/COUNTS.json"

DECISION_CLASSES = ("BUILD", "ADAPT", "INTEGRATE", "LAW", "DEFER", "DROP")
_SECTION_RE = re.compile(r"^## (2\.\d+)\s")
_SEP_RE = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+\s*$")
_P_RE = re.compile(r"\bP\d{1,2}\b")
_GENERATED_NOTE = (
    "GENERATED FILE — do not edit by hand. Source: pinned Master Plan "
    "(see plan_sha256). Regenerate with tools/gen_registry.py --write "
    "after an approved plan amendment (docs/process/plan-amendment.md); "
    "CI verifies with tools/registry_lint.py."
)


def _split_row(line: str) -> list[str]:
    """Split a markdown table row into stripped cells."""
    inner = line.strip()
    if not inner.startswith("|"):
        raise ToolError(f"table row does not start with '|': {line!r}")
    cells = [c.strip() for c in inner.strip("|").split("|")]
    return cells


def _dash_to_none(value: str) -> str | None:
    v = value.strip().strip("*").strip()
    if v in ("—", "-", ""):
        return None
    return v


def _clean_feature(raw: str) -> str:
    v = raw.strip().replace("**", "").strip()
    return re.sub(r"\s+", " ", v)


def _class_of(raw: str) -> str:
    for cls in DECISION_CLASSES:
        if re.search(rf"\b{cls}\b", raw):
            return cls
    raise ToolError(f"no recognized decision class in D cell: {raw!r}")


def parse_plan(text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lines = text.splitlines()

    # Locate §2 .. §3.
    start = next(i for i, ln in enumerate(lines) if ln.startswith("# 2."))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("# 3."))
    body = lines[start:end]

    rows: list[dict[str, Any]] = []
    section: str | None = None

    for offset, line in enumerate(body):
        sec_m = _SECTION_RE.match(line)
        if sec_m:
            section = sec_m.group(1)
            continue
        if not line.lstrip().startswith("|"):
            continue
        if section is None or not section.startswith("2.") or section == "2.10":
            continue
        if _SEP_RE.match(line.strip()):
            continue
        cells = _split_row(line)
        if cells[0] == "Feature":  # header row
            continue
        if len(cells) != 9:
            raise ToolError(
                f"plan line {start + offset + 1}: expected 9 columns, found {len(cells)}: {line!r}"
            )
        feature, dcol, owner, dep, ph, crit, sec, risk, proof = cells
        cls = _class_of(dcol)
        status = "dropped" if cls == "DROP" else "deferred" if cls == "DEFER" else "active"
        rows.append(
            {
                "id": f"F-{len(rows) + 1:03d}",
                "section": section,
                "plan_line": start + offset + 1,
                "feature": _clean_feature(feature),
                "decision_raw": dcol,
                "decision_class": cls,
                "status": status,
                "owner": owner,
                "dep_raw": dep,
                "depends_on": _P_RE.findall(dep),
                "phases_raw": ph,
                "phase_tokens": _P_RE.findall(ph),
                "criticality": _dash_to_none(crit),
                "security_tier": _dash_to_none(sec),
                "risk": _dash_to_none(risk),
                "proof": _dash_to_none(proof),
            }
        )

    reserved = parse_reserved(body, start)
    return rows, reserved


def parse_reserved(body: list[str], base_line: int) -> dict[str, Any]:
    """Parse the §2.10 reserved-interface prose (single source line)."""
    prose_idx: int | None = None
    for i, ln in enumerate(body):
        if "## 2.10" in ln:
            prose_idx = i
            break
    if prose_idx is None:
        raise ToolError("§2.10 section not found")
    prose = " ".join(body[prose_idx:])
    m = re.search(r"implementation lands later\*\*:\s*(.*?)\s*A phase may not invent", prose)
    if not m:
        raise ToolError("§2.10 reserved-interface list not found (format changed?)")
    items = [it.strip() for it in m.group(1).split("·")]
    interfaces: list[dict[str, Any]] = []
    for it in items:
        if not it:
            continue
        name, _, rest = it.partition(" ")
        covers = rest.strip()
        if covers.startswith("(") and covers.endswith(")"):
            covers = covers[1:-1].strip()
        if covers.endswith("."):  # sentence period on the last item
            covers = covers[:-1]
        snake = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name).lower()
        interfaces.append(
            {
                "id": snake,
                "name": name,
                "covers": covers,
            }
        )
    if not interfaces:
        raise ToolError("§2.10 parsed zero reserved interfaces")
    freeze_m = re.search(r"At the (P\d{1,2}) contract freeze", prose)
    rule_m = re.search(r"(A phase may not invent.*?P5-T10\)\.)", prose)
    return {
        "freeze_phase": freeze_m.group(1) if freeze_m else None,
        "rule": rule_m.group(1) if rule_m else None,
        "plan_line": base_line + prose_idx + 1,
        "interfaces": interfaces,
    }


def build_features_doc(rows: list[dict[str, Any]], plan_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": PLAN_FILE,
        "plan_sha256": plan_sha,
        "plan_sections": "2.1–2.9",
        "generated_by": "tools/gen_registry.py",
        "note": _GENERATED_NOTE,
        "features": rows,
    }


def build_reserved_doc(reserved: dict[str, Any], plan_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": PLAN_FILE,
        "plan_sha256": plan_sha,
        "plan_section": "2.10",
        "generated_by": "tools/gen_registry.py",
        "note": _GENERATED_NOTE,
        "freeze_phase": reserved["freeze_phase"],
        "rule": reserved["rule"],
        "plan_line": reserved["plan_line"],
        "interfaces": reserved["interfaces"],
    }


def build_counts(rows: list[dict[str, Any]], reserved: dict[str, Any], plan_sha: str) -> dict[str, Any]:
    by_section: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_crit: dict[str, int] = {}
    by_sec: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for r in rows:
        by_section[r["section"]] = by_section.get(r["section"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        c = r["criticality"] or "none"
        by_crit[c] = by_crit.get(c, 0) + 1
        s = r["security_tier"] or "none"
        by_sec[s] = by_sec.get(s, 0) + 1
        by_class[r["decision_class"]] = by_class.get(r["decision_class"], 0) + 1
    return {
        "schema_version": 1,
        "source": PLAN_FILE,
        "plan_sha256": plan_sha,
        "generated_by": "tools/gen_registry.py",
        "note": _GENERATED_NOTE,
        "total_rows": len(rows),
        "reserved_interface_count": len(reserved["interfaces"]),
        "by_section": dict(sorted(by_section.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_criticality": dict(sorted(by_crit.items())),
        "by_security_tier": dict(sorted(by_sec.items())),
        "by_decision_class": dict(sorted(by_class.items())),
    }


def dump_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100000)


def _load_committed_yaml(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.exists():
        raise ToolError(f"missing generated file: {rel} (run tools/gen_registry.py --write)")
    with open(path, encoding="utf-8") as fh:
        try:
            return yaml.safe_load(fh)
        except Exception as exc:
            raise ToolError(f"YAML parse failure in {rel}: {exc}") from exc


def diff_rows(
    committed: list[dict[str, Any]],
    generated: list[dict[str, Any]],
    label: str,
) -> list[str]:
    out: list[str] = []
    if len(committed) != len(generated):
        out.append(f"{label}: row count differs (committed {len(committed)} vs plan {len(generated)})")
        return out
    for i, (c, g) in enumerate(zip(committed, generated)):
        if c != g:
            fields = [k for k in g if c.get(k) != g.get(k)]
            extra = [k for k in c if k not in g]
            detail = ", ".join(
                f"{k}: {c.get(k)!r} != {g[k]!r}" for k in fields[:4]
            ) or "field set differs"
            if extra:
                detail += f" | committed-only fields: {extra}"
            out.append(f"{label}[{i}] ({g.get('id', '?')}): {detail}")
    return out


def run_check(root: Path) -> tuple[dict[str, Any], list[str]]:
    """Regenerate in memory and compare against the committed registry.

    Returns (info, failures). Fail-closed: the plan pin must be present
    and matching, otherwise the registry is untrustworthy.
    """
    plan = root / PLAN_FILE
    if not plan.exists():
        raise ToolError(f"missing plan file: {PLAN_FILE}")
    plan_sha = sha256_file(plan)

    pin_file = root / PLAN_SHA_FILE
    if not pin_file.exists():
        raise ToolError(f"missing plan pin file: {PLAN_SHA_FILE} (registry is untrustworthy without it)")
    pinned = pin_file.read_text(encoding="utf-8").strip().split()[0]
    if pinned != plan_sha:
        raise ToolError(f"plan pin mismatch before registry check: {pinned} != {plan_sha}")

    rows, reserved = parse_plan(plan.read_text(encoding="utf-8"))
    fails: list[str] = []

    feat = _load_committed_yaml(root, FEATURES_FILE)
    fails += diff_rows(feat.get("features", []), rows, "features.yaml")
    for key in ("schema_version", "source", "plan_sha256"):
        if feat.get(key) != build_features_doc(rows, plan_sha)[key]:
            fails.append(f"features.yaml: top-level {key!r} differs from generated")

    res = _load_committed_yaml(root, RESERVED_FILE)
    fails += diff_rows(res.get("interfaces", []), reserved["interfaces"], "reserved-interfaces.yaml")
    for key in ("freeze_phase", "rule", "plan_sha256"):
        if res.get(key) != build_reserved_doc(reserved, plan_sha)[key]:
            fails.append(f"reserved-interfaces.yaml: top-level {key!r} differs from generated")

    counts_path = root / COUNTS_FILE
    if not counts_path.exists():
        fails.append(f"missing generated file: {COUNTS_FILE}")
    else:
        committed_counts = json.loads(counts_path.read_text(encoding="utf-8"))
        fresh_counts = build_counts(rows, reserved, plan_sha)
        for key, val in fresh_counts.items():
            if committed_counts.get(key) != val:
                fails.append(f"COUNTS.json: {key} differs (committed {committed_counts.get(key)!r} vs plan {val!r})")
        extra = set(committed_counts) - set(fresh_counts)
        if extra:
            fails.append(f"COUNTS.json: unexpected keys {sorted(extra)}")

    info = {
        "tool": "registry_lint",
        "mode": "check",
        "plan_sha256": plan_sha,
        "pin_verified": True,
        "rows": len(rows),
        "reserved": len(reserved["interfaces"]),
    }
    return info, fails


def cmd_check(root: Path) -> int:
    from _common import emit

    info, fails = run_check(root)
    return emit(False, info, fail_messages=fails)


def cmd_write(root: Path) -> int:
    plan = root / PLAN_FILE
    if not plan.exists():
        raise ToolError(f"missing plan file: {PLAN_FILE}")
    plan_sha = sha256_file(plan)
    rows, reserved = parse_plan(plan.read_text(encoding="utf-8"))

    (root / FEATURES_FILE).parent.mkdir(parents=True, exist_ok=True)
    (root / FEATURES_FILE).write_text(dump_yaml(build_features_doc(rows, plan_sha)), encoding="utf-8")
    (root / RESERVED_FILE).write_text(dump_yaml(build_reserved_doc(reserved, plan_sha)), encoding="utf-8")
    (root / COUNTS_FILE).write_text(
        json.dumps(build_counts(rows, reserved, plan_sha), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {FEATURES_FILE} ({len(rows)} rows), {RESERVED_FILE} ({len(reserved['interfaces'])} interfaces), {COUNTS_FILE}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gen_registry.py",
        description="Derive (or verify) the Feature Registry from the pinned Master Plan.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate docs/registry/* from the plan")
    mode.add_argument("--check", action="store_true", help="fail on any drift between plan and committed registry")
    add_common_flags(parser)
    args = parser.parse_args()

    def run() -> int:
        root = Path(args.repo or ".").resolve()
        return cmd_write(root) if args.write else cmd_check(root)

    main_with_usage_guard(run)


if __name__ == "__main__":
    main()
