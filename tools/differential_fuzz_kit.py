"""tools/differential_fuzz_kit.py — generators + pair configs for the
byte-differential oracle (split from tools/differential_fuzz.py under the
P11-T0-e touched-file size law; same responsibility split as the
gen_shield_vectors driver/kit/families trio).

Pairs: themes / settings / commands (P9-T0-a) + shield (P11-T2, DoD-3).
The shield generator's input-domain scope (recorded, not hidden):
  * single well-formed {method,args} frames per spawn — the refusal and
    evaluation surface, same law as the other three pairs; multi-frame
    session fuzzing is out of scope (state parity is pinned by the 307
    golden vectors + the corpus replay instead);
  * DEFAULT backend flags only — the both-state flag coverage
    (xr_shield_v1, build channels) lives in the golden vectors;
  * the strict-JSON parse-rejection carve-out of the driver applies
    unchanged (frames here are well-formed JSON; hostile VALUES, not
    hostile encoding).
Determinism: seeded rng only; no clock, no RNG state outside the seed
(now_mono/as-of values are generated, never read).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

from shield_vectors_kit import (BUNDLE, CTX, LIST1, STATE_EMPTY, ctx,
                                slot, state_v3)

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

def pair_configs(xr_core: Path, fake_dir: Path) -> dict[str, dict[str, Any]]:
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
            "make": [str(xr_core / "commands/tests"), "build"],
            "gen": commands_gen,
        },
        "shield": {
            "host": [str(xr_core / "shield/tests/build/shield_host")],
            "fake": sh("shield.py"),
            "make": ["make", "-C", str(xr_core / "shield/tests"), "build"],
            "gen": shield_gen,
        },
    }


# ---------------------------------------------------------------------------
# shield pair (P11-T2, DoD-3): the xr_shield_v1 {method,args} surface
# ---------------------------------------------------------------------------

SHIELD_JUNK_FIELDS = ("ghost", "x", "unknown_field")


def _rand_url(rng: random.Random) -> str:
    scheme = rng.choice(("https", "http", "xr", "ftp", ""))
    host = rng.choice(("tracker.example", "ads.example", "ok.example",
                       "a.b.c.example", "EXAMPLE.COM",
                       _rand_str(rng, 8, "abc.-1")))
    port = rng.choice(("", ":8080", ":0"))
    path = rng.choice(("", "/", "/a.js", "/x/y/z.png",
                       "/" + _rand_str(rng, 6, "ab/._-")))
    tail = rng.choice(("", "?q=1", "#f", " "))
    return f"{scheme}://{host}{port}{path}{tail}"


def _rand_domain(rng: random.Random) -> str:
    return rng.choice(("tracker.example", "ads.example", "example.com",
                       "ok.example", "", _rand_str(rng, 6, "ab.-")))


def _rand_bundle(rng: random.Random) -> dict:
    b = dict(BUNDLE)
    r = rng.random()
    if r < 0.5:
        return b
    if r < 0.75:
        lst = dict(LIST1)
        rules = [dict(x) for x in LIST1["rules"]]
        for rule in rules:
            if rng.random() < 0.4:
                rule["filter"] = rng.choice(
                    ("||x.example^", "|left", "right|", "*wild*", "##.ad",
                     "@@||ok.example^", _rand_str(rng, 8, "ab|*^.")))
            if rng.random() < 0.2:
                rule["action"] = rng.choice(
                    ("block", "allow", "redirect", "replace", "bogus", ""))
        lst["rules"] = rules
        b["lists"] = [lst] if rng.random() < 0.85 else []
    if r < 0.85:
        b["bundle_version"] = rng.randint(-2, 9)
    return b


def _rand_scope(rng: random.Random, sid: str) -> dict:
    s: dict[str, Any] = {
        "scope_id": sid,
        "reason": rng.choice(("user", "user-allow", "false-positive",
                              "temporary", "work", "")),
    }
    dim = rng.choice(("site", "rule_id", "identity", "workspace", "list_id",
                      "none"))
    if dim == "site":
        s["site"] = rng.choice(("example.com", "tracker.example", ""))
    elif dim == "rule_id":
        s["rule_id"] = "r-1"
        s["list_id"] = "l1"
    elif dim == "identity":
        s["identity"] = rng.choice(("xr:a", "profile-b"))
    elif dim == "workspace":
        s["workspace"] = f"ws{rng.randint(1, 3)}"
    elif dim == "list_id":
        s["list_id"] = rng.choice(("l1", "l2"))
    if rng.random() < 0.3:
        s["expiry_mono"] = rng.randint(-1, 900)
    return s


def _rand_ctx(rng: random.Random) -> dict:
    kw: dict[str, Any] = {}
    if rng.random() < 0.3:
        kw["tab_type"] = rng.choice(("workspace", "normal", "guest"))
        kw["workspace"] = f"ws{rng.randint(1, 2)}"
    if rng.random() < 0.2:
        kw["first_party"] = rng.random() < 0.5
    return ctx(_rand_url(rng), _rand_domain(rng),
               identity=rng.choice(("xr:a", "xr:b", "", "XR:A")),
               request_class=rng.choice(("kScript", "kNavigation",
                                         "kSubresource", "kImage", "kFetch",
                                         "")),
               **kw)


def shield_gen(rng: random.Random, _data: Any = None) -> dict[str, Any]:
    r = rng.random()
    if r < 0.35:  # match — the evaluation surface
        args: dict[str, Any] = {"context": _rand_ctx(rng),
                                "bundle": _rand_bundle(rng)}
        for flag in ("engine_alive", "engine_poisoned", "kill_switch_on",
                     "route_bound"):
            if rng.random() < 0.12:
                args[flag] = rng.random() < 0.5
        if rng.random() < 0.3:
            args["scopes"] = [_rand_scope(rng, f"s{i}")
                              for i in range(rng.randint(1, 3))]
        if rng.random() < 0.3:
            args["now_mono"] = rng.randint(-1, 10 ** 9)
        return {"method": "match", "args": args}
    if r < 0.45:  # event-emit — the living block-event-v1 row
        a: dict[str, Any] = {
            "action": rng.choice(("kBlocked", "kAllowed", "kRedirected",
                                  "kReplaced", "kBogus")),
            "context": _rand_ctx(rng),
            "seq": rng.randint(-1, 10 ** 6),
            "ts_millis": rng.randint(0, 10 ** 12),
            "why_code": rng.choice(("rule-blocked", "scope", "engine",
                                    "bogus", "")),
        }
        if rng.random() < 0.4:
            a.update(bundle_version=rng.randint(0, 9), list_id="l-1",
                     rule="||tracker.example^", rule_id="r-1",
                     tab_id=rng.randint(-1, 99))
        return {"method": "event-emit", "args": a}
    if r < 0.53:  # exception-add
        a = {"scope": _rand_scope(rng, f"ex-{rng.randint(1, 9)}")}
        if rng.random() < 0.3:
            a["scopes"] = [_rand_scope(rng, f"ex-{rng.randint(10, 19)}")]
        return {"method": "exception-add", "args": a}
    if r < 0.60:
        return {"method": "bundle-load", "args": {"bundle": _rand_bundle(rng)}}
    if r < 0.67:  # apply — monotonic state machine
        st = rng.random()
        state = (STATE_EMPTY if st < 0.4 else
                 state_v3() if st < 0.8 else
                 {"active": slot("xr-default", 4),
                  "lkg": slot("xr-default", 3),
                  "pins": [slot("xr-default", 3), slot("xr-default", 4)],
                  "last_apply_mono": rng.randint(-1, 300)})
        return {"method": "apply",
                "args": {"bundle": _rand_bundle(rng), "state": state,
                         "now_mono": rng.randint(-5, 1000)}}
    if r < 0.72:
        return {"method": "Status",
                "args": {"identity": {"value": rng.choice(
                             ("xr:a", "", "XR:A", "xr:" + _rand_str(rng, 4, "ab")))},
                         "origin": {"scheme": rng.choice(("https", "http", ""))}}}
    if r < 0.77:
        a = {"site": rng.choice(("example.com", "news.example", "")),
             "on": rng.random() < 0.5}
        if rng.random() < 0.3:
            a["expiry_mono"] = rng.randint(-1, 900)
        if rng.random() < 0.2:
            a["scopes"] = [_rand_scope(rng, "ex-a")]
        return {"method": "site-toggle", "args": a}
    if r < 0.81:
        return {"method": "exception-sweep",
                "args": {"scopes": [_rand_scope(rng, f"s{i}")
                                    for i in range(rng.randint(0, 3))],
                         "now_mono": rng.randint(-1, 1000)}}
    if r < 0.84:
        return {"method": "exception-remove",
                "args": {"scope_id": rng.choice(("ex-1", "no-such", ""))}}
    if r < 0.87:
        return {"method": "bundle-check",
                "args": {"bundle": _rand_bundle(rng)}}
    if r < 0.90:
        return {"method": "RecentEvents",
                "args": {"limit": rng.choice((0, 1, 256, 65536, 70000, -1))}}
    if r < 0.96:
        m = rng.choice(("posture", "page-states", "flag-status", "debug-page"))
        a = {}
        if rng.random() < 0.25:
            a[rng.choice(SHIELD_JUNK_FIELDS)] = rng.randint(0, 9)
        return {"method": m, "args": a}
    if r < 0.98:  # unknown methods (the closed refusal vocabulary)
        return {"method": rng.choice(("bogus-method", "", "MATCH",
                                      _rand_str(rng, 5, "ab-"))),
                "args": {}}
    # protocol-shape junk: well-formed JSON envelope, wrong arg TYPES
    return {"method": rng.choice(("match", "apply", "event-emit")),
            "args": rng.choice((5, "str", [], None, True))}

