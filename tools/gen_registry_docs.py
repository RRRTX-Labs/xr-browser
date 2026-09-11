#!/usr/bin/env python3
"""tools/gen_registry_docs.py — registry document shape + drift compare (P10-T0-d).

Split out of tools/gen_registry.py by responsibility: the PARSER (plan §2
text -> rows) stays in gen_registry.py; the EMITTER/COMPARATOR (rows ->
features/reserved/COUNTS documents, canonical YAML, committed-vs-generated
drift) lives here. Pure refactor — no behavior change; the 400-LOC law is
absorbed by splitting, not by compressing comments (the P7 lesson).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from _common import PLAN_FILE, ToolError

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML not importable ({exc}); install pinned dev deps") from exc

_GENERATED_NOTE = (
    "GENERATED FILE — do not edit by hand. Source: pinned Master Plan "
    "(see plan_sha256). Regenerate with tools/gen_registry.py --write "
    "after an approved plan amendment (docs/process/plan-amendment.md); "
    "CI verifies with tools/registry_lint.py."
)


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


load_committed_yaml = _load_committed_yaml
