# docs/state/research-log-P10.md — the 9 research items (cited-or-UNVERIFIED)

Law: each item cites `path:line@pin` via `build/upstream/fetch.py`/raw URL +
fetch date, or reads `UNVERIFIED (deferred to P<n>)`. Never assert from
memory where a fetch settles it. Sandbox facts (what this machine can and
cannot run) are recorded per item where they matter.

## 1. `//chrome/updater` at the pin

**UNVERIFIED (deferred to P16/farm) — partially answered from the pin's
DEPS identity, honestly.** The pinned Chromium source tree is NOT checked
out in this sandbox (the repos are `xr-core` + `xr-browser`; the checkout
mount is farm-side), so `chrome/updater/*` file:line citations at
`d04cdb24…` cannot be produced from a live read. What IS pinned and cited:
the DEPS chromium identity `chromium: "152.0.7977.82" @ d04cdb24…`
(`xr-browser/DEPS`, sha-verified by `check-pin-alive`), and the
client↔server boundary WE own is fully specified from our side:
`release/server/spec/render-31.md` (request grammar closed; response = the
frozen 3.1 subset `docs/contracts/update-manifest-31.schema.json`) +
`docs/release/updater-integration.md` (to land with the farm glue, HG-31).
What a fork must supply (app id `labs.rrrtx.xr`, update URL, per-user vs
per-machine registration) is specified in `xr-core/update/README-integration.md`
as OUR contract to the farm, explicitly marked pending a live
`//chrome/updater` read. **P11+ inherits:** produce the file:line citations
at the pin before wiring CRX packaging.

## 2. Protocol 3.1 conformance edges (incl. delta/puffin)

**PARTIALLY VERIFIED (server side, live here); client-side delta support
UNVERIFIED (deferred to P11).** Server-side edges are pinned by the
conformance corpus (`release/server/tests/conformance.json`, 51 cases):
the `)]}'` prefix is optional and stripped once (cases
`happy-nightly-with-prefix`, `double-prefix`); unknown fields refused at
every level; non-canonical versions refused (`bad-version-*`); error
responses are canonical `{detail,error}` 400s. Client requirements we
enforce on our side: `appid`, canonical 4-part version, `status: ok`,
closed manifest/urls/epoch/signature sets (frozen schema +
`update/core/manifest.cc` parse law; golden vectors verify/51). Delta
packages: **UNVERIFIED** — whether the pinned client supports partial
patches and with which codec (puffin/courgette) needs the farm checkout
(research item 1's dependency); the ≥60% size win is NOT measured and is
recorded honestly in `docs/release/handbook.md` limitations.

## 3. Signature/epoch model + minisign + sigstore/rekor

**Design VERIFIED as implemented (our side); external format details
UNVERIFIED where a fetch is required.** In-tree updater authentication:
transport-only assumptions are exactly what we removed — the core carries
no transport datum, TLS-independence is a tested matrix
(`test_verify_policy`: bad-TLS+good-sig ⇒ accept; good-TLS+bad-sig ⇒ deny;
unknown key ⇒ deny; expired/foreign epoch ⇒ deny). Minisign: our artifact
format row is `minisign-ed25519` with `sig:`-prefixed armored signatures
(`release/keys/key-hierarchy.md`); the EXACT minisign file-format bytes
(Trusted Comment lines, global signature) are **UNVERIFIED (deferred to
P13/T3-execution)** — no minisign binary in the sandbox (recorded below),
and we do not invent crypto: the injected verifier interface
(`update/core/verifier.h`) takes the format as an injected binding.
sigstore/rekor: the honest answer is recorded in
`docs/contracts/release-attestation-v1.md` — offline verification with a
PINNED public key is what we demonstrate (`tools/attest.py --verify`,
real here); a public-good rekor dependency (fulcio/rekor reachability,
log-trust) is **UNVERIFIED (deferred)** and the DoD row stays
BLOCKED/human-gated (HG-38).

## 4. Per-platform signing reality (CA/B 2023–2026, SmartScreen, Apple, Linux)

**UNVERIFIED (deferred to HG-37 procurement) — the command shapes are
real and tested; the procurement facts are not fetched.** The exact CI
argv is pinned and stub-tested (`build/signing/platform_argv.py` +
`build/signing/tests/argv_stub_test.py`): `codesign --force --options
runtime --timestamp --entitlements …`, `xcrun notarytool submit --wait`,
`xcrun stapler staple`, `signtool sign /fd SHA256 /tr … /td SHA256`,
`osslsigncode verify`. Linux repo signing is REAL here (gpg present;
`build/signing/tests/test_signing_p10.sh`: 14 cells incl. tamper/wrong-key).
Windows EV/HSM hardware-key rules, SmartScreen reputation accrual
mechanics, and Apple Developer ID lead times: **UNVERIFIED (deferred to
HG-37)** — they are procurement facts needing official-source fetches at
ceremony time; this log deliberately does not assert them from memory.
The sandbox has NO minisign/codesign/notarytool/osslsigncode/signtool
(recorded in the phase evidence); missing-key cells SKIP-visible (77).

## 5. Cohort/rollout control plane + auditable epoch revocation

**VERIFIED as our own minimal semantics (marked ours); Chromium-internal
rollout metadata at the pin UNVERIFIED (deferred to P38).** Our design:
bucketing is client-side from a LOCAL random install id
(`update/core/cohort.cc`: sha256(install_id ‖ 0x1f ‖ channel) first 8
bytes BE mod buckets — no server-side personal state; vectors pinned:
79/41/94); the server compares the client-declared bucket against the
channel ramp with the off-by-one pinned in data + conformance
(`cohorts.yaml` ramp law, corpus `beta-boundary-49-in`/`-50-out`). The
auditable revocation notice (signed, monotonic seq, sticky revoked,
forced manual path) is our design, implemented + drilled
(`tools/rollout_drill.py` cells 6–8). What Chromium's own
components/rollout metadata does at the pin: **UNVERIFIED (deferred to
P38)** — it needs the farm checkout; our semantics are marked ours.

## 6. Crash-rate auto-halt input (P38 seam)

**Decision VERIFIED as implemented + tested; in-tree crash reporting at
the pin UNVERIFIED (deferred to P38).** Decision: **no-auto-halt until
P38** — an absent telemetry input must never be read as "healthy" (that
would be telemetry by assumption), and it must not silently halt either;
until P38 every ramp pause point requires a HUMAN advance, which makes
the halt-on-unknown question moot while keeping the interface stable.
Recorded in `release/rollout/policy.yaml` (`crash_hook.on_absent_input`,
rationale inline) + enforced dev-channel-only assertion (drill cell 10:
`crash_hook.channels_allowed == ["dev"]`). What crashpad/crash services
exist at the pin: **UNVERIFIED (deferred to P38)** — farm checkout read.

## 7. cargo vet/audit from a std-only project — the zero-crate outcome

**VERIFIED (local reasoning + toolchain facts); crates.io registry state
UNVERIFIED (not needed).** The deployable uses **ZERO external crates**
(`release/server/rust/Cargo.toml` — no `[dependencies]` section at all;
`#![forbid(unsafe_code)]`): sha256, canonical JSON, and the state machine
are implemented against std alone (`release/server/rust/src/lib.rs`) and
proved byte-identical to the reference on the 51-case corpus. Zero crates
is the security win (no supply chain to vet; `cargo vet`/`cargo deny`
have nothing to analyze — the vet lane on the hosted runner still runs
and will confirm "no dependencies"). Whether a packed-integer version
crate would be *needed*: no — `parse_version` is 25 lines of std
(`parse_version` in lib.rs), matching the Python reference exactly
(conformance cases `bad-version-*`). Sandbox note: no cargo/rustc here —
the Rust lane is runner-ready and proves itself hosted.

## 8. Runner capabilities (ubuntu-latest cargo/rustc/go)

**VERIFIED for cargo/rustc by an ACTUAL run (2026-09-11):**
`core-hardening` run 34604887643, job server-conformance (103280790981),
step output — `cargo 1.98.1 (797e8a9bc 2026-08-05)`,
`rustc 1.98.1 (48a229cea 2026-09-01)` (transcript:
`evidence/P10/logs/research8-runner-probe.txt`). The same run ANSWERED
two more capability facts honestly: ubuntu-latest python carries **no
PyYAML** (the fuzz-fleet lane failed with ModuleNotFoundError and now
pins `pyyaml==6.0.3` explicitly), and the freshness job needed its
xr-core checkout step (fixed). `go` remains **UNOBSERVED** (no Go surface
exists in P10; no lane printed a go version — not asserted). The
blind-written Rust deployable needed exactly the first-compile fixes the
no-local-toolchain rule predicted; the committed corpus caught them
locally once a toolchain was present (rustc 1.85 via apt: 51/51
byte-identical).

## 9. Signing-key custody (HSM/KMS options, unfunded-team class)

**UNVERIFIED (deferred to HG-36 procurement) — prices/terms deliberately
NOT asserted.** The ceremony (`release/keys/ceremony.md`) names the
YubiKey-PIV class as the candidate root custody (two devices: primary +
sealed backup; PIV slot 9a; air-gapped generation; two-person witness)
because the exact commands (`ykman piv keys generate 9a …`) are written
to be executed at ceremony time — but current prices, terms, and the
firmware policy are procurement facts that must be fetched when HG-36
opens, not asserted from memory in a repo. The cloud-HSM alternative
(KMS-class per-key quotas + attestation) is named as the fallback with
the same honest deferral. What IS verified: the tooling refuses to
generate release-marked keys (negative fixture
`signing_release_keygen_refused` / the guard in
`build/signing/platform_argv.py`), and no key material exists anywhere
(`tools/secret_scan.py --all`, 786 files, clean).

---

## Upstream symbols our code calls (host file:line, this repo — no Chromium)

The update stack calls NO upstream/Chromium symbols: `update/core/**` is
std-only C++20 (the hygiene gate `tools/core_hygiene_check.py` proves
zero Chromium includes across 5 cores / 84 files), the host
(`update/host/update_host.cc`) is stdio-JSON only, and the deployable
(`release/server/rust/`) is std-only Rust. The only live external calls
in P10 tooling are the P3 allowlisted choke point
(`build/upstream/fetch.py` → chromiumdash `fetch_releases`, cited live in
`release/notes/train-152.md`, fetched 2026-09-11).
