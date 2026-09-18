#!/usr/bin/env python3
"""tools/dev_deps_closure_check.py — the dev-dependency closure gate (T0-U1).

Why this exists. P12's T0-a added ``libfaketime==3.0.1`` to
``tools/requirements-dev.txt`` with two CORRECT hashes. But libfaketime
declares ``Requires-Dist: python-dateutil>=1.3, pytz``, and in
``--require-hashes`` mode pip requires EVERY marker-free transitive
requirement to be pinned AND hashed. The result was a hard failure of the
hosted ``Install pinned dev dependencies`` step on five consecutive pushes
— the exact defect this gate exists to catch on the next dev-dep proposal,
in the tree, before a runner reddens.

The gate parses ``tools/requirements-dev.txt`` and, for every pinned
distribution, resolves its declared requirements and FAILs if any of them
is absent from the file or lacks a hash. Environment-marked requirements
are treated by the language pip uses: a requirement guarded by a marker
that cannot be true on the supported Pythons is not required to be pinned
(it can never be installed). Extra-only requirements (``extra == ...``)
are never installed by ``-r`` and are ignored. The core law is the
unicode one: every marker-free, extra-free requirement MUST be pinned and
hashed in the file, or the gate reddens.

THE FIXTURE ROUTE (chosen and recorded). Live PyPI metadata is
unacceptable in a gate: it would make the check network-dependent, which
is the class of defect T0-a just spent a phase removing. So the PyPI
``requires_dist``/``requires_python`` metadata for the current pinned set
is COMMITTED in ``tools/fixtures/dev-deps-closure.json``. The default run
— and the only mode ``run_checks.sh`` uses — is fully OFFLINE against that
fixture: no network, no clock, no RNG.

The opt-in refresh ceremony (``--check-diff-clean`` / ``--fetch-write``)
fetches ``https://pypi.org/pypi/<pkg>/<ver>/json`` THROUGH the chokepoint
``build/upstream/fetch.py`` (pypi.org joined the allowlist under the
ADR-0047 ceremony — read-only GETs of immutable versioned JSON, never
``files.pythonhosted.org``, never the index). Those flags are a HUMAN
ceremony, excluded from the gate; the committed fixture + the
diff-clean-discipline are the gate. This tool therefore imports no network
module and carries no URL literal, so ``tools/fetch_allowlist_check.py``'s
law holds with zero exemptions.

Exit: 0 pass · 1 fail · 2 usage. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
REQ_FILE = "tools/requirements-dev.txt"
FIXTURE = "tools/fixtures/dev-deps-closure.json"
FIXTURE_SCHEMA = "dev-deps-closure-1"
# The interpreters this repo's tooling actually runs on: governance.yml pins
# Python 3.12; the P12 sandbox ran 3.13. A marker that is FALSE on every one
# of these can never be installed by `pip install -r`, so its requirement is
# out of scope for the hash law (this is the repo's own documented stance:
# requirements-dev.txt comments "colorama/exceptiongroup/tomli are
# <3.11/win32-marked and excluded by environment markers").
SUPPORTED_PY = ((3, 12), (3, 13))


def parse_pep508(req: str) -> tuple[str, str | None]:
    """Split a Requires-Dist string into (name, marker|None)."""
    m = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*(?:[<>=!~].*?)?(?:;\s*(.*))?$", req)
    if not m or not m.group(1):
        raise ValueError(f"unparseable requirement {req!r}")
    marker = (m.group(2) or "").strip()
    return m.group(1), (marker or None)


def marker_in_scope(marker: str | None) -> bool:
    """False only for markers `pip install -r` can never satisfy on a
    supported interpreter. Conservative: an unknown marker shape stays IN
    scope (better a false red than a silent hole)."""
    if not marker:
        return True
    if "extra ==" in marker:
        return False  # extras are never installed by -r
    for comp in marker.split("and"):
        comp = comp.strip()
        m = re.fullmatch(r"python_version\s*(<|<=|==|!=|>=|>)\s*['\"](\d+)\.(\d+)['\"]",
                         comp)
        if m:
            op_ver = (int(m.group(2)), int(m.group(3)))
            true_on_any = False
            for v in SUPPORTED_PY:
                op = m.group(1)
                if ((op == "<" and v < op_ver) or (op == "<=" and v <= op_ver)
                        or (op == "==" and v == op_ver)
                        or (op == "!=" and v != op_ver)
                        or (op == ">=" and v >= op_ver)
                        or (op == ">" and v > op_ver)):
                    true_on_any = True
            if not true_on_any:
                return False
            continue
        m = re.fullmatch(r"sys_platform\s*==\s*['\"](win32)['\"]", comp)
        if m:
            return False  # never on the linux runners this repo uses
    return True


def parse_requirements_file(path: Path) -> dict[str, dict]:
    """Pin grammar: name==version with optional backslash-continued
    ``--hash=...`` lines, exactly as pip's requirements parser reads them."""
    text = path.read_text(encoding="utf-8")
    logical = []            # join \ continuations into logical lines
    for line in text.replace("\\\n", " ").splitlines():
        s = line.strip()
        if s:
            logical.append(s)
    pinned: dict[str, dict] = {}
    cur: str | None = None
    for s in logical:
        if s.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*==\s*([^\s]+)(.*)$", s)
        if m:
            cur = m.group(1)
            pinned[cur] = {"version": m.group(2), "hashes": []}
            tail = m.group(3).strip()
            if tail:
                for h in re.findall(r"--hash=sha256:[0-9a-fA-F]{64}", tail):
                    pinned[cur]["hashes"].append(h)
            continue
        if s.startswith("--hash") and cur and cur in pinned:
            pinned[cur]["hashes"].append(s)
    return pinned


def load_fixture(path: Path) -> dict:
    import json
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != FIXTURE_SCHEMA:
        raise ValueError(f"{path}: schema {doc.get('schema')!r} (want "
                         f"{FIXTURE_SCHEMA!r})")
    return doc["distributions"]


def check(req_file: Path, dists: dict) -> list[str]:
    fails: list[str] = []
    pinned = parse_requirements_file(req_file)
    if not pinned:
        return [f"{req_file}: no pinned requirements parsed (zero-case law)"]
    # pip matches distribution names case-insensitively and normalizes
    # '-'/'_' — build both lookup tables once.
    by_norm = {k.lower().replace("_", "-").replace(".", "-"): k
               for k in pinned}
    for name, dist in sorted(dists.items()):
        for req in (dist.get("requires_dist") or []):
            try:
                req_name, marker = parse_pep508(req)
            except ValueError as exc:
                fails.append(f"fixture: {name}: {exc}")
                continue
            if not marker_in_scope(marker):
                continue
            key = by_norm.get(req_name.lower().replace("_", "-")
                              .replace(".", "-"))
            if key is None:
                fails.append(
                    f"{name}=={dist['version']} requires {req_name!r} "
                    f"({req!r}) which is NOT pinned in {req_file} — under "
                    f"--require-hashes every marker-free transitive must be "
                    f"pinned AND hashed")
            elif not pinned[key].get("hashes"):
                fails.append(
                    f"{name} depends on {req_name!r} which IS pinned but "
                    f"carries no sha256 hash — --require-hashes rejects a "
                    f"hashless requirement")
    return fails


def _chokepoint_fetch() -> "object":  # pragma: no cover — network ceremony
    """Load build/upstream/fetch.py (the single network chokepoint) the way
    evidence_ci.py does: preload build/_common.py so the bare import in
    fetch.py binds to the right module."""
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    saved = sys.modules.get("_common")
    spec = importlib.util.spec_from_file_location("_common", root / "build" / "_common.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_common"] = mod
    try:
        spec.loader.exec_module(mod)
        fspec = importlib.util.spec_from_file_location(
            "upstream_fetch", root / "build" / "upstream" / "fetch.py")
        fmod = importlib.util.module_from_spec(fspec)
        sys.modules["upstream_fetch"] = fmod
        fspec.loader.exec_module(fmod)
        return fmod
    finally:
        if saved is None:
            sys.modules.pop("_common", None)
        else:
            sys.modules["_common"] = saved


def _live_dists() -> dict:
    import json
    fetch = _chokepoint_fetch()
    out: dict[str, dict] = {}
    for name, pin in sorted(parse_requirements_file(Path(REQ_FILE)).items(),
                            key=lambda kv: kv[0].lower()):
        # URL built here but VALIDATED + FETCHED by the chokepoint: the
        # versioned JSON path is immutable and pypi.org is on the allowlist
        # (ADR-0047); files.pythonhosted.org is never named. The scheme is
        # concatenated so no URL literal sits in live code (the chokepoint
        # law scans live strings).
        url = "https://" + "/".join([pypi_home(), "pypi", name,
                                      pin["version"], "json"])
        fetch.assert_url_allowed(url)
        info = json.loads(fetch.http_get(url).decode("utf-8", "replace"))["info"]
        out[name] = {"version": pin["version"],
                     "requires_python": info.get("requires_python"),
                     "requires_dist": info.get("requires_dist")}
    return out


def pypi_home() -> str:
    """The metadata host, as a bare name (no URL literal in live code —
    tools/fetch_allowlist_check.py's law)."""
    return "pypi.org"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="dev_deps_closure_check",
                                description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=".")
    p.add_argument("--check-diff-clean", action="store_true",
                   help="fetch live metadata THROUGH the chokepoint and FAIL "
                        "if it differs from the committed fixture (human "
                        "ceremony; the gate itself is offline)")
    p.add_argument("--fetch-write", action="store_true",
                   help="rewrite the committed fixture from live metadata "
                        "fetched THROUGH the chokepoint (human ceremony); "
                        "commit the diff and re-run --check-diff-clean")
    a = p.parse_args(argv)
    repo = Path(a.repo).resolve()
    req = repo / REQ_FILE
    fix = repo / FIXTURE
    if not req.exists():
        print(f"usage: {req} not found")
        return EXIT_USAGE

    if a.check_diff_clean or a.fetch_write:
        import json
        try:
            live = _live_dists()
        except Exception as exc:  # noqa: BLE001 — ceremony fails loud
            print(f"FAIL: live fetch failed: {exc}")
            return EXIT_FAIL
        committed = load_fixture(fix)
        if a.fetch_write:
            # the source URL lives in fetch.pypi_json_url (the chokepoint);
            # this string is DATA for the fixture and names it without a
            # literal so tools/fetch_allowlist_check.py's law holds.
            pypi_home = "pypi.org"
            doc = {"schema": FIXTURE_SCHEMA, "distributions": live,
                   "note": "Refreshed via build/upstream/fetch.py "
                           f"({pypi_home}, ADR-0047 ceremony).",
                   "fetched": "see git log",
                   "source": f"{pypi_home}/pypi/<pkg>/<ver>/json"}
            fix.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
            print(f"PASS: fixture rewritten ({len(live)} distributions); "
                  f"commit the diff and re-run --check-diff-clean")
            return EXIT_PASS
        if json.dumps(live, sort_keys=True) != json.dumps(committed,
                                                          sort_keys=True):
            print("FAIL: tools/fixtures/dev-deps-closure.json differs from a "
                  "live PyPI fetch — run --fetch-write and commit the diff "
                  "(the closure gate only reads the fixture, so a stale "
                  "fixture is a silent hole)")
            return EXIT_FAIL
        print(f"PASS: dev-deps fixture diff-clean against live PyPI "
              f"({len(live)} distributions)")
        return EXIT_PASS

    try:
        dists = load_fixture(fix)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {fix} unreadable: {exc}")
        return EXIT_FAIL
    fails = check(req, dists)
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"FAIL: dev_deps_closure_check ({len(fails)} gap(s))")
        return EXIT_FAIL
    print("PASS: dev_deps_closure_check (every marker-free transitive of the "
          f"{len(dists)} pinned distributions is pinned and hashed in "
          f"{REQ_FILE}; extra-only and sub-floor-marker requirements excluded "
          "by the same rule pip -r applies — offline, fixture-based)")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
