# Research log — P7 (one command registry, four views, window chrome)

The P7 working notes: what was decided, what was found, and why. This doubles as
the review packet for the new `command-host-protocol v1` contract registered in
`docs/contracts/registry-post-freeze.md` (P6-T5 pattern).

## Research items — cites / UNVERIFIED (the brief's 8 RESEARCH REQUIRED)

Each item is either **cited** (a fetch settles it in-sandbox) or **UNVERIFIED**
(deferred to a named phase; nothing asserted from memory as fact).

1. **Lit pin.** CITED — `lit@3.3.3`, BSD-3-Clause, live-verified 2026-09-08
   against `registry.npmjs.org` (reachable in-sandbox); integrity hash in
   `ui/toolchain/package-lock.json`; eval `docs/dependencies/lit.yaml` (P1) +
   the npm-integrity pins. Lit renders the views; no state logic in TS.
2. **WebUI + CSP at the pin.** PARTIALLY CITED — the CSP we target
   (`script-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'`),
   no inline JS, and external-script-only shell are the standard Chromium
   `chrome://` model; the built bundle is re-scanned by `check-bundle.js`.
   **UNVERIFIED:** the exact `content/browser/webui/` file:line that emits the
   served-page CSP header at pin `d04cdb24` — to be confirmed at P16 glue (the
   off-tree toolchain does not depend on it; the header contract is documented
   as data in `docs/webui-toolchain.md`).
3. **UI hook points at the pin.** CITED for the 4 registered hooks (fetched at
   `d04cdb24` through `build/upstream/fetch.py` + round-tripped):
   `chrome/browser/ui/views/BUILD.gn`, `…/toolbar/app_menu.cc`,
   `…/toolbar/toolbar_view.cc`, `…/frame/browser_frame_view.cc`. **UNVERIFIED:**
   the tabstrip per-tab tint path (Brave `brave_tab_container` prior art) and
   the `ui/base/accelerators/` table are not fetched in-sandbox (deferred to
   P16; the ≤12 patch does not touch them).
4. **Palette ranking.** CITED — subsequence-fuzzy scoring + deterministic
   tie-breaks implemented in `commands/core/matcher.cc`; complexity target
   (2000 commands × 32-char query ≤ 5 ms p99 core) **met in-sandbox at 972 µs**
   (`bench-results.json`, seed 20260908); tie-break determinism pinned by
   `golden-rankings.json` + the matcher tests. The 50/150 ms *end-to-end* is
   HG-31 (farm), not claimed in-sandbox.
5. **Shortcut conflict detection.** CITED by design — the conflict classes
   (reserved-by-browser, system-reserved, duplicate) mirror the standard
   Chromium accelerator-reservation model and are implemented + tested in
   `commands/core/shortcuts.cc` (browser-reserved F11/CTRL+SHIFT+I/F12,
   system-reserved ALT+F4/CTRL+ESC, deny-by-default). **UNVERIFIED:** the exact
   `chrome/browser/ui/…/global_shortcut*` file:line at the pin (deferred P16).
6. **a11y / RTL rule sets.** CITED — ARIA APG "Combobox with Listbox Popup"
   (the `aria-activedescendant` SR path), `:focus-visible` rings, and CSS
   logical properties for RTL are encoded as structural linters
   (`tools/a11y_lint.py`, `tools/rtl_lint.py`); the linters are ours (not
   axe-core). **UNVERIFIED:** specific axe-core rule IDs/versions (we encode the
   structural law, not axe-core itself).
7. **Reproducible bundling.** CITED — `esbuild@0.28.2` + integrity,
   `npm ci --ignore-scripts` (0 vulnerabilities, `npm audit` 2026-09-08),
   no-sourcemap/no-clock bundle; two-build byte-identity asserted by
   `repro-check.sh` (sha256 `96159b4b…`).
8. **Menu-model generation.** CITED by design — the registry→MenuModel-JSON
   generator (`tools/menu_model_check.py` via the ref-fake) emits data
   (`menu-model.json`) testable headlessly today; `--check` goldens it.
   **UNVERIFIED:** the exact Chromium `ToolbarActionView`/`MenuModel` file:line
   mapping (P16 glue consumes the JSON).

## Decisions

- **Four views over ONE registry.** The palette, menus, shortcut editor and help
  index are all renderings of `roster_v1.json` (20 commands). A "registry" that
  has a private palette list + a private menu list + a private help list is the
  anti-pattern this phase exists to kill; the menu-model + query + list methods
  all read the *same* C++ registry.
- **Dispatch in C++ only.** The `invoke` gate (source-tag whitelist → id
  whitelist → availability → danger-class confirmation) lives in
  `commands/core/dispatch.cc`. TS never sees an unknown id and never decides
  whether a page-originated command may run. The palette is a *client* of the
  gate, not a peer.
- **Placeholders are disabled-with-reason, never absent.** `tor.open` is
  registered with the `tor.engine-ready` predicate (it denies until P31), so the
  help index shows "disabled — Tor engine not wired (P31)". §10 forbids coming-
  soon rails; a disabled row with a reason is not a rail.
- **The flag is the kill-switch, not a feature toggle.** `xr_command_registry_v1
  = false` ⇒ stock chrome + empty registry + all four views render nothing. It is
  the Plan P7 rollback row. Kept until P13 (expiry note 1/2 in
  `build/gn/argsets/flags.yaml`, 2/2 in `registry-post-freeze.md`).

## Findings

- **Byte-parity is the freeze mechanism, not a lint.** The `command-descriptor-
  v1` contract is P5-frozen; P7 *implements to it*. The host protocol (the new
  P7 contract) is frozen by **31-case C++⇄Python byte-parity** (`fakes/commands.py`
  is the reference). Two concrete parity gotchas, both now baked into the harness:
  1. **Canonical JSON must ASCII-escape non-ASCII.** C++ `JsonValue::Canonical()`
     emits `\u2014`/`\u00a7`; the Python fake must use `ensure_ascii=True` (a raw
     `—` is not byte-identical). Hand-escaping is forbidden.
  2. **Route every request as `{"method","args"}`.** A bare positional hits the
     C++ `main()` hardcoded *non-sorted* parse-failure branch (parser detail, not
     byte-matchable). The JSON-with-method branch is deterministic + sorted on
     both backends. The single malformed case is compared by **error code**
     (the top-level error object differs only in key order: C++ error-first,
     Python sorted) — never by the raw line.
- **The `kMaxTier1=9` budget is enforced at load, not at render.** A 10th
  tier-1 command is rejected by the registry *at registration*
  ("would be the 10th tier-1 control"). `menu_model_check.py`'s Tier-1≤9 check
  is a belt-and-suspenders re-assertion on the generated model; the C++ registry
  test is the primary gate. The negative is a *load rejection*, so a
  10-tier-1 roster never produces a 10-item model.
- **The ≤12 hook patch is verified against the REAL pinned bytes.**
  `build/webui/patch_roundtrip.py` fetches the 4 pinned hook files at
  `d04cdb24…` through `build/upstream/fetch.py`, applies the patch, verifies,
  reverts (byte-exact), and runs a **negative** (a perturbed anchor must FAIL).
  9 files (4 hook + 5 payload) ≤ 12; never-list (all under
  `chrome/browser/ui/**`) enforced independently of `allowed_roots`.
- **The WebUI build's only network edge is the lock.** `npm ci --ignore-scripts`
  with `esbuild`'s binary as an integrity-pinned optionalDependency means no
  postinstall runs. `repro-check.sh` proves two builds are byte-identical (the
  R1 rung).

## What is deliberately NOT here

- **No fake grit/resources integration.** `ui/BUILD.gn` is a placeholder that
  names the P16 farm integration; a hand-rolled `.grd`/`.mojom` would be the
  "fake integration" the plan refuses. The off-tree toolchain is the stable
  deliverable.
- **No second registry for the chrome.** The identity/trust chrome slots are
  carried by the `xr_command_bridge` seam; they read the *same* P6 trust-
  bindings, not a parallel store.

## Budget + parity evidence (pointers)

- p99 core: `xr-core/commands/tests/bench-results.json` (972 µs ≤ 5 ms).
- parity: `tools/tests/test_p7_commands_tools.py::test_parity_31_valid_plus_1_malformed`.
- patch round-trip: `evidence/P7/patch-roundtrip.txt`.
- repro: `evidence/P7/repro.txt`.
