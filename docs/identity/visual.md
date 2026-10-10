# Identity chrome: how an identity looks (P14-T4)

Status: the state-to-visual mapping is DATA with a law and structural
snapshots, all run here (P14-CLOSE C-1). Pixel rendering is NOT-RUN: this
sandbox has no browser to paint with (method at the bottom).

## One table, two consumers

`xr-core/ui/identity-chrome/states.json` (schema
`identity-chrome-states-v1`) is the only place that says how an identity
state looks:

* **states**: `standard`, `disposable`, `tor-unbound`. Each carries a CSS
  class, an accessible name, an SR string id, a route string id and (where
  the state needs one) a window border;
* **layouts**: `top` and `vertical` (bar plus glyph plus label), `compact`
  (bar plus glyph), `rail` (dot plus glyph). Every layout carries a glyph or
  an initial, so **colour never stands alone**;
* **geometry and tokens**: a 2 px bar, a 1 px edge, an 8 px dot. Every
  colour is a theme token from `ui/themes/tokens.json`; no hex value is
  typed into the chrome.

The pure core (`ui/identity-chrome/chrome-core.ts`) and the lit element
(`identity-chrome.ts`) read it, and so does the snapshot generator.

## Contrast is computed, never typed in

For every layout × theme the generator computes the bar or dot contrast
against the strip surface (minimum 3.0 for non-text) and the pill text
contrast (minimum 4.5). A mark below its minimum gets an edge line in the
`text` token, and the snapshot records that edge. Today there are 20
snapshots (4 layouts × 5 themes: light, dark, dusk, prairie,
high-contrast) recording 28 edges.

## The laws (run here)

* `tools/identity_chrome_check.py`: every state has a unique class, an
  accessible name, an SR string and a route string that exist in the grdp;
  every sample's name, colour and glyph equal the identity core's template
  table (`xr-core/identity/core/templates.cc`, read live); every contrast
  pair is computed per theme, and pill text below 4.5 is a FAIL with no
  fallback. A planted missing SR string, a missing grdp message, a template
  colour drift and a hand-edited snapshot each redden it
  (`tools/negatives/p14c_c1.sh`).
* `tools/identity_chrome_check.py --check`: regenerates the 20 structural
  snapshots in `ui/identity-chrome/snapshots/` and diffs them byte for
  byte. It never rewrites in-tree.
* `ui/identity-chrome/tests/identity-chrome.test.mjs`: the core's
  `structure()` output must equal every committed snapshot, so the
  component and the snapshots cannot drift apart.
* `tools/attention_check.py`: the chrome is a silent surface; its strings
  carry no escalation vocabulary.

Transcript: `evidence/P14/logs/c1-identity-chrome.txt`.

## NOT-RUN (methods, not surrogates)

* Pixels in each layout × theme, and what a sighted user actually sees:
  `docs/qa/browser-harness.md#identity-chrome-visual`.
* SR announcements on a real screen reader:
  `docs/qa/browser-harness.md` (SR announcement audit, P14-T4).
