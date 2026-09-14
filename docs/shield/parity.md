# XR Shield v1 — parity: corpus provenance, bands, refresh, NOT-RUN capture (P11-T8)

Tool: `tools/shield_parity.py` (exit 0 pass · 1 band failure · 2 usage ·
77 visible SKIP when the real lane has no shim locally — never silent).

## 1. What the bands are measured ON

The committed corpus: `xr-core/shield/tests/corpus/parity-corpus-v1.json`
(schema `xr-shield-parity-corpus` v1) — **1,533 cases** (≥1,500 floor) over
420 bundles, 21 instances, 20 rule classes.

* **Provenance:** pure enumeration by
  `xr-core/shield/tests/corpus/gen_parity_corpus.py` — no RNG, no wall
  clock, machine-derivable. Synthetic hosts/filters only; every bundle
  carries the attribution string "XR P11 synthetic parity fixture
  (CC0-1.0)". **No third-party list text is redistributed**, so the R6
  (EasyList-family licensing) constraints are not engaged by this corpus.
  The published adblock `.crate` tarball carries NO upstream test tree
  (cargo strips `tests/` at publish time — research-log R2/D7), so the
  crate's own unit tests cannot be the conformance source; this corpus +
  the parity job are.
* **Expected verdicts** are derived by the generator's OWN implementation
  of the documented v1 semantics (the `core/fake_engine.h` law comments) —
  NOT by running any engine — and committed. `gen_parity_corpus.py --check`
  proves the file byte-identical to deterministic regeneration (transcript:
  `evidence/P11/logs/t8-corpus-gen-check.txt`).
* **Bands (plan §11 L312 + brief T8):** action agreement ≥ 98 % (±2 %);
  false-positive rate ≤ 0.5 % of expected-allow cases (FP = expected allow,
  engine said block/redirect/replace; denominator 714 expected-allow cases);
  provenance (rule/list recovery) agreement ≥ 98 %.
* **Lanes:** `fake` (local — `xr-core/fakes/shield.py decide_match`, the
  byte-parity Python mirror; compares action, why_code, engine_decision,
  rule_id) and `real` (`--engine real --shim libxr_shield_engine.so` — the
  vendored adblock-rust through ctypes, the SAME C ABI the C++ core
  injects; runs in the core-hardening `shield-vendor` lane). Provenance on
  `provenance-divergence-D5`-tagged cases is reported, not enforced
  (class D-5 below).

Recorded results: fake lane 100.0 % / 0.0 % FP / 100.0 % provenance, FN 0
(`evidence/P11/logs/t8-shield-parity-fake.txt`); real-lane numbers are
cited machine-resolvably (`ci-run` rows) in `evidence/P11/evidence.json` —
never copied here as prose.

## 2. Refresh method

1. Regenerate: `python3 xr-core/shield/tests/corpus/gen_parity_corpus.py`
   (deterministic; `--check` must stay diff-clean in `run_checks.sh`).
2. Replay both lanes: `python3 tools/shield_parity.py` (fake, local) — the
   real lane runs in the `shield-vendor` lane; locally it SKIPs visibly
   (exit 77) without the shim.
3. Any change to matcher bytes (`shield/core/{bundle,match,context,
   fake_engine}.*`) re-arms the mutation-freshness law: the FULL shield
   mutation matrix re-runs and `docs/state/mutation-scores.json` records
   the new pin (precedent: the 2026-09-14 alignment, 396/396 at
   `866387a`).

## 3. Divergence log

`docs/shield/parity-divergences.md` — classes D-1…D-9, each with owner,
status and disposition. Upstream-first items (D-7 host-END anchor, D-8
trailing-`*` strip, D-9 lowercased surface) were resolved in the engine AND
both mirrors at once (xr-core `866387a` + xr-browser alignment commit),
then the corpus was regenerated and re-pinned byte-identical across
backends. D-4 (fusion provenance on product bundles) stays a farm-lane
measurement; D-6 is the capture corpus below.

## 4. The 1,000-site capture corpus: NOT-RUN (HG-31), method committed

Live-traffic FP measurement needs the farm browser rig — no browser exists
in any lane yet, and no live-traffic FP claim is made anywhere. The method
is committed so the farm lane needs no new decisions:
`docs/qa/browser-harness.md` §Farm runbook + §Shield capture set
(1,000-site live-traffic capture, per-tab ring, categorization by list
provenance). Until it runs, the FP band rides the vendored synthetic
corpus ONLY, and the gap is recorded as divergence class D-6 + human gate
HG-31 (`evidence/P11/human-gates.md`).
