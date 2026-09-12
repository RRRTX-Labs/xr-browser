#!/usr/bin/env python3
"""tools/vendor_rust_graph.py — crate-graph resolution for the P11-T1 vendorer.

Split from tools/vendor_rust.py (touched-file size law): this module is the
pure logic — lock parsing, feature-aware build-closure BFS, semver tie-breaks,
SPDX license verdicts, GHSA advisory matching. No writes, no CLI. The truth
model:

  * the crate's OWN published Cargo.lock (inside the sha256-pinned tarball)
    is the resolution truth: a dependency edge whose crate the lock never
    resolved belongs to a feature that is OFF at the pin — skipped;
  * dev-dependencies (and optional bench deps with a dev-dep twin) are never
    vendored: the honest --offline boundary is the build graph, recorded in
    supply-chain/PROVENANCE.md;
  * optional deps are included only when reachable from the enabled feature
    set (default features + parent-requested features, honoring
    default-features = false) AND the lock's resolved version satisfies the
    edge's semver requirement — over-inclusion is inert, under-inclusion
    breaks --offline, and the hosted `cargo build --offline` is the final
    empirical gate (UPDATING.md documents the iteration).
"""
from __future__ import annotations

import tomllib

# DR-04: copyleft-only licensing (the red class ADR-0001 names — its tokens
# are spelled in the dependency evals, never in code files: license_audit
# fails code hits unconditionally) is a red. MPL-2.0 is our own license.
# Disjunctions are judged branch-wise; the CHOSEN branch is recorded in
# supply-chain/licenses.json (compliance is a decision, not a shrug).
ALLOWED_LICENSES = {"MPL-2.0", "MIT", "Apache-2.0", "BSD-2-Clause",
                    "BSD-3-Clause", "ISC", "Zlib", "Unicode-3.0",
                    "Unicode-DFS-2016", "0BSD", "CC0-1.0", "BSL-1.0",
                    "NCSA", "Unlicense", "AFL-2.0"}
ALLOWED_EXCEPTIONS = {"LLVM-exception", "LLVM-exception-2.0", "OpenSSL"}


def parse_lock(text: str) -> dict[tuple[str, str], dict]:
    d = tomllib.loads(text)
    out = {}
    for p in d["package"]:
        out[(p["name"], p["version"])] = {
            "checksum": p.get("checksum"),
            "source": p.get("source", ""),
            "deps": [tuple(x.split(" ", 1)) if " " in x else (x, None)
                     for x in p.get("dependencies", [])],
        }
    return out


def _semver_key(v: str) -> tuple:
    parts = v.split("-", 1)[0].split(".")
    return tuple(int(x) if x.isdigit() else 0 for x in parts[:3])


def semver_satisfies(version: str, req: str) -> bool:
    """Caret/tilde/exact/bare requirement check — used for lock tie-breaks
    and optional-edge validation only (the lock is the primary truth)."""
    req = req.strip()
    v = _semver_key(version)
    if req.startswith("^"):
        r = _semver_key(req[1:])
        if r[0] > 0:
            return v >= r and v[0] == r[0]
        if r[1] > 0:
            return v >= r and v[0] == 0 and v[1] == r[1]
        return v == r
    if req.startswith("~"):
        r = _semver_key(req[1:])
        return v >= r and v[0] == r[0] and v[1] == r[1]
    if req.startswith("="):
        return v == _semver_key(req[1:])
    if req.startswith(">="):
        return v >= _semver_key(req[2:])
    if req.startswith("<="):
        return v <= _semver_key(req[2:])
    if req.startswith(">"):
        return v > _semver_key(req[1:])
    if req.startswith("<"):
        return v < _semver_key(req[1:])
    # bare requirement = caret (cargo semantics): ^1.0 == >=1.0, <2.0
    return semver_satisfies(version, "^" + req)


class Dep(dict):
    """A manifest dependency edge with its cargo metadata."""

    @property
    def name(self) -> str:
        return self["name"]

    @property
    def is_dev(self) -> bool:
        return self["dev"]

    @property
    def optional(self) -> bool:
        return self["optional"]

    @property
    def req(self) -> str | None:
        return self["req"]

    @property
    def features(self) -> list:
        return self["features"]

    @property
    def default_features(self) -> bool:
        return self["default_features"]


def manifest_dep_edges(manifest: dict) -> list[Dep]:
    """Every edge over [dependencies], [build-dependencies] and all
    [target.*.dependencies] tables. The published/normalized manifest marks
    dev-deps with kind='dev' AND keeps separate dev tables; optional bench
    deps appear in [dependencies] with optional=true + a dev twin."""
    edges: list[Dep] = []

    def emit(table: dict, dev: bool) -> None:
        for alias, v in table.items():
            v = v if isinstance(v, dict) else {"version": str(v)}
            edges.append(Dep(
                name=v.get("package") or alias,  # renamed deps resolve real
                req=v.get("version"),
                dev=dev or v.get("kind") == "dev",
                optional=bool(v.get("optional")),
                features=list(v.get("features", [])),
                default_features=v.get("default-features", True),
            ))

    for table, dev in (("dependencies", False), ("dev-dependencies", True),
                       ("build-dependencies", False)):
        emit(manifest.get(table, {}), dev)
    for tgt in manifest.get("target", {}).values():
        for table, dev in (("dependencies", False),
                           ("dev-dependencies", True),
                           ("build-dependencies", False)):
            emit(tgt.get(table, {}), dev)
    return edges


def enabled_closure(manifest: dict, requested: set[str]) -> set[str]:
    """Transitive closure of enabled feature names starting from `requested`
    (usually {'default'} plus features parents asked for)."""
    feats = manifest.get("features", {})
    seen: set[str] = set()
    stack = list(requested)
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        for val in feats.get(f, []):
            if val.startswith("dep:"):
                seen.add(val[4:].split("/")[0])  # activated optional dep
            else:
                base = val.lstrip("?").split("/")[0]
                if base and base in feats:
                    stack.append(base)
                elif base:
                    seen.add(base)  # implicit optional-dep feature
    return seen


def child_requested(manifest: dict, seen: set[str],
                    dep_name: str) -> set[str]:
    """Features this crate's enabled set requests ON a child crate: 'c/f'
    and weak 'c?/f' values, plus the child's own default unless the edge
    says default-features = false (edge handled by the caller)."""
    out: set[str] = set()
    feats = manifest.get("features", {})
    for name in seen:
        for val in feats.get(name, []):
            if "/" in val and not val.startswith("dep:"):
                weak = val.startswith("?")
                c, sub = val.lstrip("?").split("/", 1)
                if c == dep_name and (not weak or sub):
                    out.add(sub)
    return out


def resolve(lock: dict, name: str, req: str | None) -> tuple[str, str] | None:
    """The lock entry for a dep edge. None = the lock never resolved it
    (feature OFF at the pin) or no candidate satisfies the requirement."""
    cands = [(n, v) for (n, v) in lock if n == name]
    if not cands:
        return None
    if req:
        ok = [c for c in cands if semver_satisfies(c[1], req)]
        if not ok:
            return None
        cands = ok
    if len(cands) == 1:
        return cands[0]
    return max(cands, key=lambda c: _semver_key(c[1]))


def build_closure(lock: dict, root_manifest: dict,
                  root_nv: tuple[str, str], load_manifest,
                  root_features: set[str] | None = None,
                  ) -> tuple[set[tuple[str, str]], dict]:
    """Feature-aware BUILD closure. `load_manifest(nv) -> dict` fetches +
    verifies a crate's published Cargo.toml (caller owns bytes/sha256).
    Returns (closure-without-root, manifests)."""
    manifests: dict[tuple[str, str], dict] = {root_nv: root_manifest}
    want: set[tuple[str, str]] = set()
    # queue items: (nv, requested-features, parent-nv)
    queue = [(root_nv, root_features or {"default"}, None)]
    visited: set[tuple[tuple[str, str], frozenset[str]]] = set()
    while queue:
        nv, requested, _parent = queue.pop(0)
        key = (nv, frozenset(requested))
        if key in visited:
            continue
        visited.add(key)
        man = manifests.get(nv) or load_manifest(nv)
        manifests[nv] = man
        seen = enabled_closure(man, requested)
        for e in manifest_dep_edges(man):
            if e.is_dev:
                continue
            if e.optional and e.name not in seen:
                continue  # feature OFF at this pin
            dep = resolve(lock, e.name, e["req"])
            if dep is None:
                if e.optional:
                    continue  # lock never resolved it: OFF at the pin
                raise SystemExit(
                    f"error: non-optional dep {e.name} (req {e["req"]}) of "
                    f"{nv[0]} {nv[1]} is missing from / incompatible with "
                    "the crate lock — inconsistent pin, refusing")
            child_req = child_requested(man, seen, e.name)
            if e.default_features:
                child_req = child_req | {"default"}
            child_req |= set(e.features)
            if dep not in want:
                want.add(dep)
            queue.append((dep, child_req, nv))
    want.discard(root_nv)
    return want, manifests


def _split_top(expr: str, op: str) -> list[str]:
    """Split on ' op ' at paren depth 0 only (SPDX expressions nest)."""
    parts, depth, cur = [], 0, ""
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and expr.startswith(f" {op} ", i):
            parts.append(cur)
            cur = ""
            i += len(op) + 2
            continue
        cur += ch
        i += 1
    parts.append(cur)
    return parts


def license_verdict(expr: str | None) -> tuple[bool, str | None]:
    """(ok, chosen-branch) for one SPDX expression. AND (top level, paren-
    aware) first: every part must be ok, chosen = the whole expression. Then
    OR: any allowed branch -> ok (chosen = first allowed branch).
    'WITH <exc>': the exception must be known; legacy 'MIT/Apache-2.0' is
    the old crates.io spelling of OR. Unknown identifiers are NOT ok."""
    if not expr:
        return (False, None)
    expr = expr.strip()
    and_parts = _split_top(expr, "AND")
    if len(and_parts) > 1:
        if all(license_verdict(x)[0] for x in and_parts):
            return (True, expr)
        return (False, None)
    or_parts = _split_top(expr, "OR")
    if len(or_parts) > 1:
        for branch in or_parts:
            ok, chosen = license_verdict(branch)
            if ok:
                return (True, chosen)
        return (False, None)
    base = expr.strip("()").strip()
    if base != expr and (" OR " in base or " AND " in base):
        return license_verdict(base)  # a fully parenthesized group: recurse
    if "/" in base and " " not in base:  # legacy MIT/Apache-2.0
        return license_verdict(base.replace("/", " OR "))
    if " WITH " in base:
        base, exc = base.split(" WITH ", 1)
        if exc.strip() not in ALLOWED_EXCEPTIONS:
            return (False, None)
    base = base.strip()
    return (base in ALLOWED_LICENSES,
            base if base in ALLOWED_LICENSES else None)


def range_hit(version: str, rng: str | None) -> str:
    """Verdict for one GHSA vulnerable_version_range: 'hit', 'miss', or
    'NEEDS-REVIEW' (an unparseable range is never silently a miss)."""
    if not rng:
        return "NEEDS-REVIEW"
    v = _semver_key(version)
    try:
        for clause in rng.split(","):
            clause = clause.strip()
            for op in (">=", "<=", "==", "=", ">", "<"):
                if clause.startswith(op):
                    bound = _semver_key(clause[len(op):].strip())
                    ok = {">=": v >= bound, "<=": v <= bound,
                          "==": v == bound, "=": v == bound,
                          ">": v > bound, "<": v < bound}[op]
                    if not ok:
                        return "miss"
                    break
            else:
                return "NEEDS-REVIEW"
        return "hit"
    except (ValueError, IndexError):
        return "NEEDS-REVIEW"


def match_advisories(vendored: set[tuple[str, str]],
                     advs: list[dict]) -> dict:
    names = {n for n, _ in vendored}
    matches, hits, reviews = [], [], []
    for a in advs:
        for vuln in a.get("vulnerabilities", []):
            pkg = vuln.get("package", {})
            eco = (pkg.get("ecosystem") or "").casefold()
            if eco not in ("cargo", "rust", "crates.io"):
                continue
            if pkg.get("name") not in names:
                continue
            for name, version in sorted(vendored):
                if name != pkg.get("name"):
                    continue
                verdict = range_hit(
                    version, vuln.get("vulnerable_version_range"))
                row = {"ghsa_id": a.get("ghsa_id"), "cve_id": a.get("cve_id"),
                       "severity": a.get("severity"), "crate": name,
                       "vendored_version": version,
                       "vulnerable_version_range":
                           vuln.get("vulnerable_version_range"),
                       "first_patched_version":
                           vuln.get("first_patched_version"),
                       "verdict": verdict}
                matches.append(row)
                if verdict == "hit":
                    hits.append(row)
                elif verdict == "NEEDS-REVIEW":
                    reviews.append(row)
    return {"hits": hits, "needs_review": reviews, "name_matches": matches}
