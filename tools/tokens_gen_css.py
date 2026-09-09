"""tools/tokens_gen_css.py — CSS-generation half of the token pipeline (P8-T2).

Split out of tools/tokens_gen.py under the 400-LOC house law (build/tests/
test_file_size_law.py): the static chrome rules + the tokens.css generator live
here; the validator/header generator/CLI stay in tokens_gen.py, which imports
gen_css from this module. Nothing here imports tokens_gen.py.

Stdlib only.
"""
from __future__ import annotations


def _css_value(token: dict, value) -> str:
    t = token["type"]
    if t == "color":
        return str(value)
    if t == "dimension":
        return f"{int(value)}px"
    if t == "font":
        return str(value)
    raise AssertionError(t)

STATIC_CSS_RULES = """
/* Focus-visible ring on every interactive control (logical, no physical L/R;
   a11y law: keyboard users MUST see where focus is). */
xr-palette input:focus-visible,
xr-palette [role="option"]:focus-visible,
xr-shortcut-editor button:focus-visible,
xr-help-index a:focus-visible,
xr-settings-shell a:focus-visible,
xr-settings-search input:focus-visible,
xr-settings-search [role="option"]:focus-visible,
xr-settings-section a:focus-visible {
  outline: var(--xr-focus-ring);
  outline-offset: 2px;
}

.xr-row {
  display: flex;
  align-items: center;
  gap: var(--xr-space-2);
  padding-inline: var(--xr-space-2);
  padding-block: var(--xr-space-1);
  border-inline-start: 3px solid transparent;
  border-radius: var(--xr-radius);
}

.xr-row[data-danger="caution"] { border-inline-start-color: var(--xr-danger-caution); }
.xr-row[data-danger="destructive"] { border-inline-start-color: var(--xr-danger-destructive); }

/* Empty-state live region (a11y: aria-live in the view; styled here). */
.xr-empty {
  padding: var(--xr-space-3);
  color: var(--xr-text-dim);
  text-align: start; /* logical — never "left" */
}

/* The identity pill / trust dial / shield chip slots (data-driven; P16 paints). */
.xr-identity-slot {
  display: inline-flex;
  align-items: center;
  gap: var(--xr-space-1);
  padding-inline: var(--xr-space-2);
  border-radius: 999px;
  background: var(--xr-surface-raised);
  border: 1px solid var(--xr-border);
}

/* Settings views (P8): the search-first shell + section/row chrome. */
.xr-settings {
  display: grid;
  gap: var(--xr-space-3);
  padding-inline: var(--xr-space-3);
  padding-block: var(--xr-space-3);
}

.xr-settings-title { font-size: var(--xr-space-4); margin: 0; }
.xr-settings-section { display: grid; gap: var(--xr-space-2); }
.xr-settings-section-title { display: flex; align-items: baseline; gap: var(--xr-space-2); }
.xr-section-id { color: var(--xr-text-dim); font-family: var(--xr-font-family-mono); }
.xr-anchor { color: var(--xr-accent); }
.xr-setting-list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--xr-space-1); }
.xr-setting-row {
  display: flex;
  align-items: center;
  gap: var(--xr-space-2);
  padding-inline: var(--xr-space-2);
  padding-block: var(--xr-space-1);
  background: var(--xr-surface-raised);
  border: 1px solid var(--xr-border);
  border-radius: var(--xr-radius);
}
.xr-setting-value { font-family: var(--xr-font-family-mono); }
.xr-setting-meta { color: var(--xr-text-dim); }
.xr-setting-badge {
  font-size: calc(var(--xr-space-3) - 2px);
  padding-inline: var(--xr-space-1);
  border-radius: var(--xr-radius);
  border: 1px solid var(--xr-border-strong);
}
.xr-settings-label { display: block; margin-block-end: var(--xr-space-1); }
.xr-settings-input {
  inline-size: 100%;
  box-sizing: border-box;
  padding-inline: var(--xr-space-2);
  padding-block: var(--xr-space-1);
  background: var(--xr-surface-raised);
  color: var(--xr-text);
  border: 1px solid var(--xr-border-strong);
  border-radius: var(--xr-radius);
}
.xr-settings-list {
  list-style: none; margin: 0; padding: 0;
  background: var(--xr-surface-raised);
  border: 1px solid var(--xr-border);
  border-radius: var(--xr-radius);
}
.xr-settings-list [role="option"] {
  display: flex; justify-content: space-between; gap: var(--xr-space-2);
  padding-inline: var(--xr-space-2); padding-block: var(--xr-space-1);
}
.xr-settings-list [role="option"][aria-selected="true"] { background: var(--xr-accent-soft); }
.xr-settings-kind { color: var(--xr-text-dim); }
.xr-unavailable { color: var(--xr-danger-caution); }
"""


def gen_css(doc: dict) -> str:
    meta = doc["tokens"]
    theme = doc["themes"]["light"]
    order = list(meta)
    L: list[str] = []
    L.append("/* Copyright 2026 RRRTX Labs")
    L.append(" * Use of this source code is governed by the MPL-2.0 license that can be")
    L.append(" * found in the LICENSE file.")
    L.append(" *")
    L.append(" * GENERATED FILE — do not hand-edit. Regenerate with")
    L.append(" *   python3 tools/tokens_gen.py   (xr-browser)")
    L.append(" * and keep `tools/tokens_gen.py --check` diff-clean in CI.")
    L.append(" *")
    L.append(" * Design tokens (Plan §10, theme-tokens-v1): ONE source")
    L.append(" * (ui/themes/tokens.json) -> tokens.css (--xr-* custom properties)")
    L.append(" * + ui/themes/tokens.h (C++ 0xAARRGGBB). RTL-logical ONLY (no")
    L.append(" * physical left/right — tools/rtl_lint.py). Views reference these")
    L.append(" * custom properties; they never hard-code colors. 'critical-red' is")
    L.append(" * reserved in data + validator (never themeable to a non-alarming")
    L.append(" * color).")
    L.append(" */")
    L.append("")
    L.append(":root {")
    for name in order:
        row = meta[name]
        v = theme[name]
        if name == "critical-red":
            L.append(f"  /* RESERVED (data+validator): never themeable to a "
                     f"non-alarming color. */")
        L.append(f"  --xr-{name}: {_css_value(row, v)};")
    # Derived vars (views rely on them; values come from tokens above).
    L.append("  /* Derived (kept from the P7 baseline, values from tokens). */")
    L.append("  --xr-danger-safe: var(--xr-text-dim);")
    L.append("  --xr-focus-ring: 2px solid var(--xr-accent);")
    L.append("}")
    L.append(STATIC_CSS_RULES)
    return "\n".join(L) + "\n"
