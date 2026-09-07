from pathlib import Path

import pytest

from resolve_args import (
    SELECTABLE,
    load_allowlist,
    merge_argsets,
    parse_argset,
    validate,
)

HERE = Path(__file__).resolve().parent
ARGSETS = HERE.parent / "argsets"


def test_merge_override_precedence():
    merged, overrides = merge_argsets({"a": "1", "b": "2"}, {"b": "3"})
    assert merged["b"] == "3"
    assert overrides == [{"flag": "b", "base": "2", "override": "3"}]


def test_parse_argset_duplicate_rejected():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".gn", delete=False) as f:
        f.write("x = 1\nx = 2\n")
        p = Path(f.name)
    with pytest.raises(Exception, match="duplicate flag"):
        parse_argset(p)
    p.unlink()


def test_allowlist_and_argsets_consistent():
    allow = load_allowlist(ARGSETS)
    common = parse_argset(ARGSETS / "xr_common.gni")
    for f in SELECTABLE:
        over = parse_argset(ARGSETS / f)
        assert validate({**common, **over}, allow) == []


def test_unknown_flag_rejected():
    allow = load_allowlist(ARGSETS)
    assert validate({"totally_unknown_flag": "1"}, allow) != []


def test_every_argset_flag_allowlisted():
    allow = load_allowlist(ARGSETS)
    common = parse_argset(ARGSETS / "xr_common.gni")
    for f in SELECTABLE:
        merged, _ = merge_argsets(common, parse_argset(ARGSETS / f))
        assert validate(merged, allow) == []
        for name in merged:
            assert name in allow, f"{f}: {name} not allowlisted"
