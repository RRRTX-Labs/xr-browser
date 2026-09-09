# Research log — Phase P8 (Stage 1): WebUI platform, Settings v0, Theme tokens v1

Each item: cite (`path:line@pin`, a URL + date, or `UNVERIFIED (deferred to
P<n>)`). Nothing relied on is left to memory where a fetch settles it. Upstream
facts were checked at the pin `d04cdb24d67b081f6cf80200ffc5233f44b61109`
(152.0.7977.82) via `build/upstream/fetch.py`.

## T0 — added-file upstream debt (root cause, P8 blocking debt)

Manifest entries may ADD files that exist at no upstream rev (P7's
`0100-ui-skeleton` payload `chrome/browser/ui/xr/*`). `rebase_bot.py:151`
(`pin_files[f] = source.file_text(from_rev, f)`) had no 404 tolerance while the
target-side fetch one line below was already wrapped (`try/except FetchError`),
so the daily canary died before producing a report:

```
$ XR_LIVE_NET=1 ./scripts/build rebase rebase --to <latest-main-sha> --dry-run --explain
error: HTTP 404 fetching https://chromium.googlesource.com/chromium/src/+/d04cdb24…/chrome/browser/ui/xr/BUILD.gn?format=TEXT   (exit 1)
```

The same latent defect sat in `promotion.py` (compat smoke `_patch_roundtrip_at`,
previously `promotion.py:144`): a FetchError there became
`return False, "target file … not fetchable"`, so any promotion would be
permanently refused while an added file is in the manifest — an added file is
absent at the candidate rev *by definition* and must not be an error.

Fix semantics (implemented in the pure engine `classify.py`, not the fetch
layer):
- a manifest file missing at the pin is an **addition**: absent at the pin AND
  absent at the target ⇒ `clean` (apply creates it);
- addition + PRESENT at the target ⇒ `path-collision` (BROKEN verdict, human
  work item — never silently renamed);
- moved-detection (`_moved_targets`) is never attempted for additions (the
  pin bytes do not exist by definition, so there is nothing to hash).
- Only a genuine `HTTP 404` counts as "missing": any other FetchError still
  fails closed (an absence is never guessed).
- `promotion.py`: 404-at-candidate ⇒ materialize the file as ABSENT and let
  `apply_patch` decide. Added file ⇒ created (clean); an upstream-DELETED hook
  file ⇒ apply failure (refusal, real re-anchor work item). Offline-deterministic.

Coverage so this cannot hide until a 02:00 UTC nightly again:
- fixture tests in `build/upstream/tests/test_upstream_suite.py`
  (added-file clean / path-collision BROKEN / mixed entry / engine-misuse
  rejections / run_rebase rows / promotion smoke accepted-added +
  refused-deleted);
- the fixture corpus gained `F-0006-added` (a patch whose file exists at NO
  rev) with per-range oracle rows;
- a NEW on-push live smoke lane in `tools/run_checks.sh`: real fetch.py
  classification from the pin to the pin (`--to <chromium_rev>`, gitiles TEXT,
  no new allowlist entries); measured 8.0 s locally (warm cache) — cold CI cost
  est. 15–30 s, comfortably inside the ~60 s note.
- one negative-gate case (added-file path-collision) ships with the P8
  negatives restructure (T8).

No gate semantics, thresholds, seeds, timeboxes or allowlist entries changed
for T0; `fetch.py` itself was NOT touched.

## T1 — settings v0 core + host + fake (xr-core 65639bf)

Settings v0 ships as a std-only C++20 core with a Python reference fake and
one byte-parity-locked stdio protocol:

- `settings/core/settings_schema_v1.json` — the single data source: 3
  sections (network/privacy/identity) + 11 typed settings (network.adblock,
  network.https-upgrade, network.route, network.tracker-block,
  privacy.letterbox, privacy.notifications, identity.storage, ...), every
  section/setting carrying its anchor, aliases, availability predicates,
  tier and security-critical marking. No hand-maintained surface list exists
  in any backend (sections/anchors/rows come from the schema).
- `settings/core/` — strict schema load (unknown schema/version/key/type
  refused), ranking core in search.cc (LOCKED DECISION "matcher share-vs-
  copy", recorded in search.h: the ~80-line fzf-class scorer is COPY-ADAPTED
  into the settings core from the P7 matcher — the settings core is std-only
  and cannot #include the P7 matcher header without pulling cross-core deps;
  the sub-word subsequence rule is the shared signal, the settings scorer is
  per-field with its own recall tuning), router, day-granular counters ledger
  (schema envelope + version; local-only; no identifiers; no timestamps
  finer than day; 90-day retention; tmp->fsync->rename; deny-preserve on an
  unreadable ledger).
- `settings/host/settings_host.cc` + `fakes/settings.py` — same protocol;
  canonical one-line JSON, byte-parity over 31+6 valid cases and malformed
  frames by error code (xr-browser `tools/tests/test_p8_settings_themes.py`).
- Recall corpus: 200 phrases generated from schema aliases (never
  hand-edited; `--check` diff-clean); measured recall 200/200 = 100.0%
  top-3 (bar >=95%). Settings suites: schema/host/fuzz/counters/recall all
  0 failures; bench: future-scale 2000-entry corpus p50 9 us / p95 16 us /
  p99 24 us — verdict MET (sub-budget 5000 us p99).
- Disposable sessions write zero bytes (filesystem-level, tested); a
  corrupt/unreadable ledger is preserved, never rewritten (deny-preserve).

## T2 — token pipeline v1 (xr-core de28f80)

One JSON source -> two generated consumers, diff-checked:

- `ui/themes/tokens.json` (schema_version 1): 40 meta tokens (colors,
  dimensions, fonts) with types/usage/pairing graph — the pairing graph is
  the audit edge set for T3.
- `xr-browser/tools/tokens_gen.py` writes `ui/themes/tokens.h` (C++20:
  colors as `uint32_t 0xAARRGGBB` — LOCKED DECISION "header type": never
  SkColor/Skia/Chromium include by design) and `ui/tokens.css`
  (`--xr-*` custom properties). The P7 hand-written tokens.css was CONVERTED
  with every value preserved 1:1 (verified var-by-var, none changed).
- Validator strictness: unknown schema/version/token/field/theme-key
  refused; duplicate keys refused; every theme covers every token; types
  enforced; `critical-red` RESERVED.
- Native consumer: the 0100-ui-skeleton patch payload now includes the
  generated header (`xr/ui/themes/tokens.h`) instead of hand-literal color
  tables; manifest round-trip at the pin.
- Generator self-negatives + `--check` diff-clean gate in xr-browser
  `tools/tests/test_p8_tokens_gen.py`.

## T3 — theme engine v0 + five built-ins + contrast core (xr-core 8102a92)

- `themes/core/contrast.{h,cc}` — WCAG 2.1 relative luminance + ratio; see
  research item 5 below for the cross-check story. Thresholds: body text
  4.5:1, large text 3:1, security_critical pairs 7:1. Where a 7:1 pairing is
  not achievable the waiver lives in the TOKEN DATA as a machine-readable
  row (`waivers: [{token,pair,best,reason}]`) — auditable, never a comment.
- `themes/core/loader.{h,cc}` — validate -> audit -> REFUSE; a failing
  theme never applies; refusal reasons are typed human-readable strings
  surfaced in the UI.
- Built-ins shipped as data in `ui/themes/tokens.json`: **light, dark,
  high-contrast + the +2 curated: dusk, prairie** (LOCKED DECISION "curated
  +2": names + rationale — both are first-party palettes with no third-party
  brand colors and no image/asset references; both pass AAA (>=7:1) on every
  security_critical pair — dusk critical-red edges 7.05/7.49/8.42:1,
  prairie 7.26/8.01/8.86:1 — so they earn their pixels per L12). **System**
  is a resolver, not a theme: it follows `system_resolution.modes`
  (light/dark/high-contrast) and carries no colors of its own.
- Light carries exactly 9 exact waiver rows (security_critical hues on light
  surfaces: the brightest canonical alarming/danger family members cap at
  4.5-5.65:1 on #fff-ish surfaces — waived in data with reasons and a 4.5
  floor: below body-text 4.5 nothing is waivable). Every waiver row is
  checked as exact data: a row on a passing pair is refused as unnecessary;
  a stale `best` is refused as mismatched (data-hygiene law). The other four
  themes carry zero waivers.
- Reserved `critical-red` law (identical in theme.cc, tokens_gen.py,
  fakes/themes.py): `r >= 0x60 AND r >= max(g,b) AND (r-min(g,b)) >= 0x60`.
  (The first attempt — channel-ratio `r>2g && r>2b` — misclassified legit
  dark-theme alarm reds and was replaced; the replacement is a recorded
  code decision, no contract change.)
- `themes/host/themes_host.cc` + `fakes/themes.py` — byte parity over 31
  valid rows + 12 hostile/malformed rows (error-code parity) + a durability
  session whose state file is byte-identical (xr-browser
  `tools/tests/test_p8_themes_tools.py`). Apply/current/list/import/
  validate-doc/system-mode/flag-status; custom import is hostile-by-default
  (64 KiB cap, raw duplicate-key scan, strict parse, schema, audit; custom
  imports carry NO waivers).
- Bench: 6-case corpus x 400 iters on the 40-token themes — avg custom
  import ~41 us, built-in apply ~20 us, worst single ~155 us — verdict MET
  (budget 100000 us); `themes/tests/bench-results.json` committed (seed
  20260909, iterations 400, machine line).
- C++ suites: test_theme 39, test_contrast 343 (incl. per-theme audit
  invariants: zero hard failures; light exactly 9 waived; none unnecessary/
  stale), test_loader 35, test_host 37 (real-binary end-to-end incl.
  cross-process durability), test_fuzz 30 s unit lane (seed 20260909) —
  all 0 failures. The 600 s campaign + mutation gate are T4.
- Host/fake durability semantics divergence fixed in the fake to mirror the
  host: missing store dir is a typed `kIoError` refusal, never auto-created.

## Open research items (P8's eight; filled as they settle)

1. NativeTheme observation surface for the payload (views-side light/dark +
   high-contrast observer API) — to cite at the pin.
2. Upstream settings-page registration surface (`chrome/browser/resources/settings`)
   — extend-not-fork evidence.
3. Grit/GRD facts (`browser_strings*.grdp` conventions, `.xtb` byte format) and
   whether `.xtb` can be produced without Chromium's grit.
4. Chromium pseudo-locale (`qyy`) behavior (expansion/accenting/mirroring).
5. WCAG 2.1 relative-luminance/contrast math — **settled at T3**: the formula
   is implemented per WCAG 2.1 (channel `c/12.92` when <=0.04045 else
   `((c+0.055)/1.055)^2.4`; ratio `(L1+0.05)/(L2+0.05)`). Page fetched
   2026-09-09 (w3.org/TR/WCAG21); the `#dfn-contrast-ratio` glossary chunk
   was not individually located in the fetched sections, so the definition is
   pinned WITHOUT page quotation by two independent implementations (C++
   `themes/core/contrast.cc` and Python `fakes/themes.py`) asserting
   byte-equal outputs over worked anchors: #767676/white = 4.54:1,
   #545454/white = 7.57:1, #8a5f00/white = 5.649:1, white/black = 21:1,
   #8a5f00 relative luminance ~0.1359.
6. Chromium forced-colors/`forced-colors-adjust` CSS conventions.
7. npm dev-dep status re-check at work date (lit/esbuild/typescript) + stdlib
   GRD-parse confirmation.
8. Isolation-card ↔ grdp interplay decision (fold vs. keep-both + gate).

## Locked decisions (P8) — recorded with rationale

1. **Curated +2 themes — dusk + prairie** (T3): first-party palettes, no
   third-party brand colors, no image/asset references; both pass AAA
   (>=7:1) on every security_critical pair (dusk 7.05-8.42:1, prairie
   7.26-8.86:1). System stays a resolver (no palette of its own).
2. **Matcher share-vs-copy** (T1): the settings scorer is a copy-adapted
   ~80-line fzf-class scorer, NOT a shared include of the P7 matcher — the
   settings core is std-only and cannot pull commands-core deps across the
   boundary; the P7 subsequence rule is reused as the sub-word signal
   (recorded in settings/core/search.h).
3. **Generated-header type** (T2): colors as `uint32_t 0xAARRGGBB` in
   `ui/themes/tokens.h` — never SkColor, no Skia/Chromium include by design
   (recorded decision, T2 commit).
4. **Host-protocol conventions** (T1/T3): every xr core ships one stdio JSON
   host + a Python reference fake; byte-parity over >=30 valid cases per
   host is the proof bar; malformed frames compare by error code; canonical
   one-line output; durability via tmp->fsync->rename; absent store-dir =
   disposable zero-byte sessions.
5. **Waivers are data, and exact** (T3): contrast waivers live in the token
   data with token/pair/best/reason; rows on passing pairs and stale `best`
   values are refused (data-hygiene law); nothing below body-text 4.5 is
   waivable.
6. **Custom imports carry no waivers** (T3): hostile-by-default — an
   imported theme must pass the full audit on its own.
7. **Bundled-font list empty** (v0) — recorded with T4 (fonts are P30
   territory; the format must not grow a font field without an amendment).
8. **Isolation-card <-> grdp relationship** — decided with T5.
