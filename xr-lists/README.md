# xr-lists — the shield list pipeline (P11-T3)

Compiles upstream-syntax filter lists into the normalized
`xr-list-bundle-v1` document, embeds and enforces attribution, and signs
the frozen `list-bundle-manifest-v1` — **lists are DATA, never code**
(DR-04; §arch 3). The client verifies with P10's `update/core` path
(pinned keys, `epoch` rotation/revocation, `seen` replay, monotonic
version, LKG fallback — `xr-core/update/core/{verify_policy,epoch,seen,
backoff,manifest}.cc`). **No new signature format, no new rollback
format.**

## Repo choice (recorded per the P11 brief's GIT/CHANGE MANAGEMENT note)

`xr-lists/` lives in **xr-browser**, not xr-core, because: (1) the
TEST-ONLY signing channel it must use (`build/signing/`) is here; (2) the
brief places the gate at `tools/list_bundle_check.py` — the house tools
dir is here; (3) the vectors, gate dispatcher and negative-canary
machinery it is governed by are all here; (4) xr-core is the `//xr`
C++/Rust tree that compiles into the browser — a Python data pipeline
would compile into nothing there; (5) the established cross-repo
direction is xr-browser tools consuming `../xr-core` (the round-trip's
host cells do exactly that), never the reverse. Recorded as D4 in
`docs/state/research-log-P11.md`.

## Tools

| tool | role | exit shape |
|---|---|---|
| `compile.py` | ABP/uBO syntax → normalized bundle + typed refusal table | 0/1/2 |
| `attribution.py` | attribution shape law + the `LICENSE.attribution.txt` sidecar | 0/1/2 |
| `sign.py` | frozen-schema manifest + detached signature (TEST channels) | 0/1/2/77 |
| `bundle_bytes.py` | the pipeline's ONE copy of the frozen canonical-bytes rules | (library) |
| `tests/roundtrip.sh` | the real matrix: gpg sign/verify/tamper/wrong-key, SKIP-visible absences, release-channel refusal, host binding, hot-pin-out, replay | 0/1 |
| `../tools/list_bundle_check.py` | the gate: frozen-schema sha256 pin, schema/binding/state laws, refusal coverage, `--check` regeneration | 0/1/2 |
| `../tools/gen_lists_compile_vectors.py` | compile vectors per directive class (≥30-case refusal table) | 0/1/2 |

## How to add a list

1. Drop the source file in `sources/` (today: **synthetic fixtures
   only** — no upstream list bytes enter the repo until the R6 licensing
   posture and a `build/upstream/fetch.py` allowlist ceremony land; the
   pipeline is proven end-to-end on self-authored CC0 fixtures).
2. Add an entry to `sources/config.json`: `name`, `path`, `attribution`.
   The attribution MUST follow the shape law (below) — `attribution.py`
   reddens anything else.
3. Bump `bundle_version` (monotonic per `bundle_id` — the apply law
   refuses downgrades and equal re-offers; that IS the replay path).
4. Run the gate: `python3 tools/list_bundle_check.py --check` (regenerates
   the whole golden package byte-identical) and
   `bash xr-lists/tests/roundtrip.sh`.
5. To hot-pin a BAD list out: remove it from the config, bump the
   version, re-sign. The hot-pin-out is signed DATA (a manifest without
   the list) — the client drops it with no network access, and a
   re-offered old bundle is refused by monotonicity (the round-trip's
   host cells test exactly this).

## Attribution requirements

Attribution rides in THREE bound places (§arch 3; R6):

1. the bundle's per-list `attribution` — required by the shield core's
   bundle grammar and INSIDE the list digest (`xr-core/shield/core/
   bundle.h`: "where T3's attribution rides"), so it cannot be stripped
   without breaking the binding;
2. the manifest's per-entry `attribution` — the frozen
   `list-bundle-manifest-v1` schema leaves `lists[]` entries free-form
   (top level is `additionalProperties:false`, so entries are the only
   schema-legal home), and the host's `bundle-check` BINDS it: a
   manifest claiming other attribution than the pinned bytes carry is
   refused (`manifest-attribution:<name>`);
3. `LICENSE.attribution.txt` — the human-readable sidecar this pipeline
   emits into the bundle package, one sha256-bound block per list.

Shape law (enforced by `attribution.py`):
`"<list name> — © <rightsholders> — <SPDX license expression> — <source>"`
— four `" — "`-separated non-empty segments; segment 1 must equal the
list name. For the EasyList family the terms are recorded in
`docs/dependencies/easylist-family.yaml` (GPL-3.0-or-later OR
CC-BY-SA-3.0 dual; DATA-only posture, never linked as code).

## What the pipeline refuses (never a silent ignore, §arch 4)

Every unsupported directive class becomes a TYPED refusal recorded in
the bundle's refusal table (`{directive, reason, count}`) — the closed
vocabulary is pinned by `tools/list_bundle_check.py` and the per-class
vectors (`docs/contracts/vectors/xr-lists-compile-v1.json`, 47 refusal
cases):

* **scriptlets** (`#%#`, `#$#`, `##+js(`) — v1 executes NONE
  (ADR-0045, `docs/shield/scriptlets.md`);
* **procedural/extended cosmetic** (`#?#`, `#@?#`, `:has(`,
  `:matches-css`, `:upward(`, …) — beyond the pinned engine's supported
  simple-selector surface;
* **regex filters** — the normalized grammar carries none (the v1 engine
  is a literal/wildcard/anchor matcher; this is a documented capability
  gap, not an oversight);
* **filter options other than `$domain=` and `$redirect=`** —
  `unsupported-option:<name>` (incl. `$important`, which would invert
  the allow-overrides-block law, `$third-party`, `$csp`, `$replace`,
  type options — v1 rules carry no party/type/priority semantics);
* **uBO preprocessor conditionals** (`!#if`) — list-level logic is not
  data;
* anything the shield core's bundle grammar would refuse at load
  (`#`/`@`/interior pipes/empty filters/regex) — refused HERE, at
  compile time: a compiled bundle that the host refuses is a compiler
  bug (the mirror of `bundle.cc ParseFilter` in `compile.py` is exact,
  and the round-trip's host cells cross-check it).

Comments (`!`) and the `[Adblock Plus 2.0]` header are STRIPPED (normal
list metadata — not refusals). Simple cosmetic selectors (`##`/`#@#`)
are carried as INERT DATA (`kind:cosmetic`) — the v1 network engine
never matches them and there is no renderer to inject into.

## Signing channels (TEST-ONLY — release stays HG-36/37)

* the real in-sandbox round-trip uses **gpg** through P10's
  `build/signing/linux_repo_sign.py` (runtime keyring in tmp — keys are
  NEVER committed); absent gpg ⇒ visible SKIP (77), never a silent pass;
* the minisign-style artifact path delegates to `build/signing/
  sign_artifact.py` (channel `dev`; the scaffold refuses release/stable);
  absent binary ⇒ visible SKIP (P10's minisign-on-CI pattern);
* `created_epoch` is a REQUIRED CLI argument — no wall clock anywhere
  (house determinism law).
