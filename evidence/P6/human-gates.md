# P6 — human gates

P6's mechanical work is complete and green; the following require humans/infra
and were NOT simulated (L24). No new gate numbers were minted by P6; the phase
feeds existing HG-26/HG-27/HG-28 and adds one BLOCKED-FARM row (HG-29 was
already registered by the plan for PrefService/mojom).

## Carried by P6

- **HG-26 — Contract ratification (S0 dual-review).** P6-born
  `policy-change-event-v1` is registered in
  `docs/contracts/registry-post-freeze.md` with review packet
  `docs/contracts/review/15-policy-change-event-v1.md`; checklist sign-offs
  are PENDING (human). The P5 registers (FROZEN.yaml/INDEX.md) are untouched.
- **HG-28 — Farm measurement re-check.** Three items re-run on reference
  hardware: (1) the 24h fuzz campaign
  (`python3 tools/policy_fuzz.py --timebox 86400 --seed <fixed>`), (2) the
  full mutation matrix (local run: 777/777, deny-guard 124/124 — re-verify on
  farm HW), (3) bench budgets (local 2-core numbers all MET with headroom;
  p99 cold 8.96µs/200, warm 0.070µs/5, snapshot 1071µs/2000).
- **HG-29 — mojom/PrefService integration (BLOCKED-FARM).** The browser-process
  service over `xr.mojom.PolicyResolver` and the real PrefService are farm-gated
  (needs the compiled bindings, HG-27 first). Until then `service_mojom.h` is
  guarded by `XR_HAVE_MOJOM_BINDINGS` (default OFF) and the stdio `policy_host`
  is the exercised seam. Reported BLOCKED-TOOLING in evidence.json; never
  simulated.
- **minisign on CI runners.** The enterprise signed path is exercised for real
  wherever the `minisign` binary exists (locally: installed and GREEN). CI
  should install it pinned (version + tarball sha256) per the actionlint
  precedent; absence degrades to a VISIBLE skip + ledger row, never a silent
  pass.

## Deviations & honesty rows (see docs/state/research-log-P6.md R9/R10)

- Two commits briefly tracked `policy/tests/build/*` binaries before
  `.gitignore` covered the path; removed from tracking, path ignored, blobs
  remain in local history (no-rewrite rule). Never pushed in an amended form.
- DCO sign-off emails on nine local commits were fixed pre-push
  (`agent@rrrtx-labs.local` → `p6-agent@users.noreply.github.com`); trees
  verified byte-identical.
- The first full-matrix mutation run was invalidated by a shared-scratch race
  (fixed: pid-unique trees) and re-run from scratch; only the re-run is cited.
- `amend_guard.py` had a directory-wide guard contradicting its own per-file
  law; fixed toward the law with 4 new direction-proving tests (R10).
- **First P6 push went red on CI** (run 34167592053): ubuntu-24.04 runners
  build fortified by default and a stray discarded-`fopen` line in
  `test_store.cc` tripped `-Werror=unused-result` there while passing on the
  un-fortified sandbox toolchain. Fixed (stray line deleted) AND prevented
  (`-D_FORTIFY_SOURCE=2` pinned into the tests Makefile — local builds are
  now exactly as strict; full fortified build clean). A second latent lane
  failure (bench grep on redirected stdout) was caught by step inspection
  and fixed in the same push. See research-log R11.
