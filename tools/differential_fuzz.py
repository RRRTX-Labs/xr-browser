#!/usr/bin/env python3
"""tools/differential_fuzz.py — the byte-differential oracle (P9-T0-a).

The anti-drift machine P9 exists to build. For each stdio-JSON host pair
(themes/settings/commands), it generates a SEEDED, DETERMINISTIC stream of
requests, runs the compiled C++ host AND the Python reference fake on the
SAME request, and fails on ANY byte difference in (exit code, stdout) — not
just a verdict difference. A difference here is a contract breach of the
"byte-identical over the whole surface" law, exactly the class T0-a found on
the theme import path.

Generic over the three {method,args} stdio pairs. The policy host is a
subcommand host (resolve/dump/watch/snapshot) with no {method,args} protocol
table, so it is NOT fuzzed here — its parity is enforced by
tools/vectors_check.py + tools/mutation_test.py (recorded in the manifest,
not silently dropped).

Input-domain scope (recorded, not hidden): the oracle generates WELL-FORMED
JSON frames — the surface the host EVALUATES (schema/contrast/duplicate/
oversize/typed refusals and every state method), where T0-a's defect lived
and where the byte-parity law governs the response. The strict-JSON
*parse-rejection* layer is excluded from byte-comparison: the two backends
are independent parsers whose error phrasing differs ("invalid number at
offset 0" vs json's "Expecting value …") — the same carve-out the P8 parity
suite already records for malformed frames (exit code + error code only).
That layer is covered by the C++ parser suite + the corpus's code-compared
parse cases. docs/state/limitations.md carries the §1.13 row.

The zero-case law: a run that executed fewer than --min-iters requests is a
FAILURE, never a pass. g++/make absent (no C++ host) => exit 77 SKIP with the
visible reason (skip-policy law).

Exit: 0 pass · 1 fail (divergence / min-iters) · 2 usage · 77 skip.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SKIP = 0, 1, 2, 77

HERE = Path(__file__).resolve().parent

BUILTINS = ("dark", "dusk", "high-contrast", "light", "prairie")
THEMES_TOKENS = ("surface", "surface-raised", "text", "accent", "critical-red",
                 "danger-caution", "danger-destructive", "trust-standard",
                 "trust-shield", "trust-fortress", "border", "code-bg")
HEX_OK = "0123456789abcdef"


def _rand_hex(rng: random.Random) -> str:
    return "#" + "".join(rng.choice(HEX_OK) for _ in range(6))


def _rand_str(rng: random.Random, n: int, alpha: str) -> str:
    return "".join(rng.choice(alpha) for _ in range(n))


# ---------------------------------------------------------------------------
# request generators (seeded; each returns a {method, args} dict)
# ---------------------------------------------------------------------------

def themes_gen(rng: random.Random, tokens: dict[str, Any]) -> dict[str, Any]:
    r = rng.random()
    if r < 0.45:
        base = rng.choice(BUILTINS)
        theme = dict(tokens["themes"][base])
        theme.pop("waivers", None)
        for _ in range(rng.randint(0, 3)):
            k = rng.choice(THEMES_TOKENS)
            theme[k] = _rand_hex(rng)
        return {"method": "import", "args": {"theme-doc":
                json.dumps(theme, separators=(",", ":"))}}
    if r < 0.60:
        # partial doc: random subset, random typed values
        doc: dict[str, Any] = {}
        for k in rng.sample(list(tokens["tokens"]), rng.randint(1, 6)):
            typ = tokens["tokens"][k]["type"]
            if typ == "color":
                doc[k] = _rand_hex(rng)
            elif typ == "dimension":
                doc[k] = rng.randint(0, 4096)
            else:
                doc[k] = "system-ui, sans-serif"
        return {"method": "validate-doc",
                "args": {"theme-doc": json.dumps(doc, separators=(",", ":"))}}
    if r < 0.80:
        hostile = rng.randrange(5)
        if hostile == 0:
            doc = json.dumps({"ghost": "#ffffff"}, separators=(",", ":"))
        elif hostile == 1:
            doc = '{"text":"#111111","text":"#222222"}'
        elif hostile == 2:
            doc = json.dumps({"critical-red": "#00aa00"},
                             separators=(",", ":"))
        elif hostile == 3:
            doc = json.dumps({"font-family-ui": "url(https://x.example/f)"},
                             separators=(",", ":"))
        else:
            doc = json.dumps({"text": 12345}, separators=(",", ":"))
        return {"method": "import", "args": {"theme-doc": doc}}
    # state methods (disposable session: deterministic in both backends)
    m = rng.choice(("list", "current", "flag-status",
                    "apply", "system-mode"))
    if m == "apply":
        return {"method": "apply", "args": {"name": rng.choice(BUILTINS)}}
    if m == "system-mode":
        return {"method": "system-mode",
                "args": {"mode": rng.choice(("light", "dark", "high-contrast"))}}
    return {"method": m, "args": {}}


def settings_gen(rng: random.Random, keys: list[str]) -> dict[str, Any]:
    r = rng.random()
    if r < 0.35:
        q = rng.choice(("container", "containers", "ads", "block", "proxy",
                        "letterbox", "notification", "https", "disposable",
                        "zzzz-no-match", _rand_str(rng, 6, "abcdefgh")))
        return {"method": "search", "args": {"query": q}}
    if r < 0.55:
        k = rng.choice(keys + ["ghost.key", "no.such", "x.y.z"])
        return {"method": "get", "args": {"key": k}}
    if r < 0.70:
        k = rng.choice(keys)
        v = rng.choice((True, False, rng.randint(0, 9), "yes", "no"))
        return {"method": "set", "args": {"key": k, "value": v}}
    if r < 0.85:
        a = rng.choice(("", "xr://settings", "xr://settings/privacy",
                        "xr://settings/network/adblock", "xr://settings/net",
                        "xr://settings/a/b/c", "xr://settings/network/nope"))
        return {"method": "router-resolve", "args": {"anchor": a}}
    m = rng.choice(("sections", "counters-dump", "schema-dump", "flag-status"))
    return {"method": m, "args": {}}


def commands_gen(rng: random.Random, ids: list[str]) -> dict[str, Any]:
    r = rng.random()
    if r < 0.30:
        g = rng.choice(("", "tab", "window", "identity", "dial", "no-such"))
        return {"method": "list", "args": ({} if not g else {"group": g})}
    if r < 0.50:
        q = rng.choice(("new", "", "identity", "dial", "clear", "history",
                        "zzzz-no-match", _rand_str(rng, 5, "abcdefgh")))
        return {"method": "query", "args": {"query": q}}
    if r < 0.70:
        return {"method": "invoke",
                "args": {"id": rng.choice(ids + ["no.such.command"]),
                         "source": rng.choice(("palette", "ui-chrome",
                                               "menu", "page"))}}
    if r < 0.82:
        acc = rng.choice(("CTRL+K", "CTRL+SHIFT+L", "F11", "CTRL+ESC",
                          "CTRL+" + rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))
        return {"method": "bindings-set",
                "args": {"accelerator": acc,
                         "command_id": rng.choice(ids)}}
    if r < 0.92:
        m = rng.choice(("bindings-list", "bindings-clear", "menu-model",
                        "flag-status"))
        return {"method": m,
                "args": ({"command_id": rng.choice(ids)}
                         if m == "bindings-clear" and rng.random() < 0.5
                         else {})}
    return {"method": "register",
            "args": {"descriptor": {"id": f"test.{rng.randint(0, 999)}",
                                    "title": "T",
                                    "attention_tier": "tier1",
                                    "danger_class": "safe",
                                    "surface": "palette",
                                    "handler": "noop"},
                     "registry": {"registry_id": "reg1"}}}


# ---------------------------------------------------------------------------
# backend pair configuration (relative to the xr-core checkout)
# ---------------------------------------------------------------------------

def _pair_configs(xr_core: Path, fake_dir: Path) -> dict[str, dict[str, Any]]:
    def sh(script: str) -> list[str]:
        return [sys.executable, str(fake_dir / script)]
    return {
        "themes": {
            "host": [str(xr_core / "themes/tests/build/themes_host"),
                     "--tokens", str(xr_core / "ui/themes/tokens.json")],
            "fake": sh("themes.py") +
                     ["--tokens", str(xr_core / "ui/themes/tokens.json")],
            "make": ["make", "-C", str(xr_core / "themes/tests"), "build"],
            "gen": themes_gen,
        },
        "settings": {
            "host": [str(xr_core / "settings/tests/build/settings_host"),
                     "--schema",
                     str(xr_core / "settings/core/settings_schema_v1.json")],
            "fake": sh("settings.py") +
                     ["--schema",
                      str(xr_core / "settings/core/settings_schema_v1.json")],
            "make": ["make", "-C", str(xr_core / "settings/tests"), "build"],
            "gen": settings_gen,
        },
        "commands": {
            "host": [str(xr_core / "commands/tests/build/commands_host"),
                     "--roster",
                     str(xr_core / "commands/core/roster_v1.json")],
            "fake": sh("commands.py") +
                     ["--roster",
                      str(xr_core / "commands/core/roster_v1.json")],
            "make": ["make", "-C", str(xr_core / "commands/tests"), "build"],
            "gen": commands_gen,
        },
    }


def _run_backend(argv: list[str], req: str, cwd: Path,
                 timeout: float) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, input=req, capture_output=True, text=True,
                              cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return -1, "<timeout>"
    except OSError as exc:
        return -1, f"<exec error: {exc}>"
    return proc.returncode, proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--repo", default=".", help="xr-browser root (default: cwd)")
    ap.add_argument("--pairs", default="themes,settings,commands",
                    help="comma-separated pairs to fuzz")
    ap.add_argument("--fake-dir", default="",
                    help="fakes directory override (canary tests mutate a copy)")
    ap.add_argument("--seed", type=int, default=20260910)
    ap.add_argument("--iters", type=int, default=0,
                    help="exact request count (0 = driven by --timebox)")
    ap.add_argument("--timebox", type=float, default=120.0,
                    help="wall-clock seconds (default 120; evidence uses 600)")
    ap.add_argument("--min-iters", type=int, default=100,
                    help="fewer executed requests than this => FAIL (zero-case law)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    xr_core = (repo.parent / "xr-core").resolve()
    if not xr_core.is_dir():
        print("error: no ../xr-core sibling checkout", file=sys.stderr)
        return EXIT_USAGE

    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    if not pairs:
        print("error: --pairs is empty (zero-case law)", file=sys.stderr)
        return EXIT_USAGE

    import shutil
    if shutil.which("g++") is None or shutil.which("make") is None:
        print("SKIP: SKIP (tool absent: g++/make) — needed for: the "
              "byte-differential oracle (compiled C++ host vs Python fake); "
              "local hint: apt-get install g++ make (build-essential)")
        return EXIT_SKIP

    # host data for generators
    try:
        tokens = json.loads(
            (xr_core / "ui/themes/tokens.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        tokens = {"themes": {}, "tokens": {}}
    try:
        schema = json.loads((xr_core / "settings/core/settings_schema_v1.json")
                            .read_text(encoding="utf-8"))
        s_keys = sorted(s["key"] for s in schema.get("settings", [])
                        if isinstance(s, dict) and "key" in s)
    except (OSError, json.JSONDecodeError):
        s_keys = []
    try:
        roster = json.loads((xr_core / "commands/core/roster_v1.json")
                            .read_text(encoding="utf-8"))
        c_ids = sorted(c.get("descriptor", {}).get("id", "")
                       for c in roster.get("commands", [])
                       if isinstance(c, dict))
    except (OSError, json.JSONDecodeError):
        c_ids = []

    fake_dir = Path(args.fake_dir) if args.fake_dir else (xr_core / "fakes")
    configs = _pair_configs(xr_core, fake_dir)
    rng = random.Random(args.seed)
    deadline = time.monotonic() + args.timebox
    executed = 0
    divergences: list[dict[str, Any]] = []
    per_pair = {p: {"executed": 0, "divergences": 0} for p in pairs}

    for pid in pairs:
        cfg = configs.get(pid)
        if cfg is None:
            print(f"error: unknown pair {pid!r}", file=sys.stderr)
            return EXIT_USAGE
        host_argv = cfg["host"]
        if not Path(host_argv[0]).is_file():
            # build the host first (g++ present; visible failure if it errors)
            r = subprocess.run(cfg["make"], cwd=xr_core, capture_output=True,
                               text=True)
            if r.returncode != 0 or not Path(host_argv[0]).is_file():
                print(f"SKIP: SKIP (build failed for {pid}) — needed for: the "
                      f"differential oracle; {r.stderr.strip()[-200:]}")
                continue

    if args.iters > 0:
        total = args.iters
    else:
        total = None  # timebox-driven

    while total is None or executed < total:
        if time.monotonic() > deadline:
            break
        pid = rng.choice(pairs)
        cfg = configs[pid]
        if not Path(cfg["host"][0]).is_file():
            continue  # pair built-skipped above
        if pid == "themes":
            req_obj = themes_gen(rng, tokens)
        elif pid == "settings":
            req_obj = settings_gen(rng, s_keys)
        else:
            req_obj = commands_gen(rng, c_ids)
        req = json.dumps(req_obj, separators=(",", ":"))
        rc_h, out_h = _run_backend(cfg["host"], req, xr_core, 10.0)
        rc_f, out_f = _run_backend(cfg["fake"], req, xr_core, 10.0)
        executed += 1
        per_pair[pid]["executed"] += 1
        if rc_h != rc_f or out_h != out_f:
            per_pair[pid]["divergences"] += 1
            divergences.append({"pair": pid, "request": req,
                                "cpp_rc": rc_h, "cpp_out": out_h,
                                "fake_rc": rc_f, "fake_out": out_f})
            if len(divergences) >= 20:
                break  # report the first 20; the run already failed

    n_div = len(divergences)
    result = {
        "tool": "differential_fuzz",
        "seed": args.seed,
        "executed": executed,
        "divergences": n_div,
        "pairs": per_pair,
        "timebox": args.timebox,
    }
    if args.json:
        print(json.dumps({**result, "status": "pass" if n_div == 0 else "fail"},
                         indent=2))
    else:
        for pid, st in per_pair.items():
            print(f"pair {pid}: {st['executed']} requests, "
                  f"{st['divergences']} divergences")
        for d in divergences[:5]:
            print(f"DIVERGENCE {d['pair']}: rc cpp={d['cpp_rc']} "
                  f"fake={d['fake_rc']}")
            print(f"  request: {d['request'][:160]}")
            print(f"  cpp:  {d['cpp_out'][:200]}")
            print(f"  fake: {d['fake_out'][:200]}")
        print(f"{'PASS' if n_div == 0 else 'FAIL'}: differential_fuzz "
              f"({executed} requests, {n_div} divergences)")

    if executed < args.min_iters:
        print(f"FAIL: differential_fuzz executed {executed} < min-iters "
              f"{args.min_iters} (zero-case law)")
        return EXIT_FAIL
    return EXIT_PASS if n_div == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
