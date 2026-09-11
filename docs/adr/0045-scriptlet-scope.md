# ADR-0045: XR Shield v1 ships ZERO scriptlets — typed refusals instead of the plan's "engine-supported superset"

- **Status:** PROPOSED (drafted by the P11 coding agent; ratification rides
  HG-26's queue — agents draft, humans decide, L24)
- **Date:** 2026-09-12
- **Deciders (humans):** Security lead + Network/Shield lead (the list
  channel is T10's remote-behavior-control surface; scriptlets would
  escalate it to remote code execution)
- **Plan anchor:** Plan §8.2's "no list-executed logic beyond
  engine-supported scriptlet sandbox" (the "superset" phrasing), P11
  brief §arch 4 ("ship only what the pinned adblock-rust genuinely
  sandboxes; every other directive class ⇒ typed refusal, never a silent
  ignore"), research item R9b (scriptlet posture — UNVERIFIED until a
  cited read at the pin)
- **Evidence:** `docs/shield/scriptlets.md` (threat analysis + the full
  refusal table), `xr-lists/compile.py` (the refusal path),
  `docs/contracts/vectors/xr-lists-compile-v1.json` (47 refusal cases,
  every reachable family covered), `xr-lists/tests/roundtrip.sh` (the
  refusals cross-checked against the compiled C++ host),
  `docs/state/research-log-P11.md` R9b

## Context

The plan says Shield may run scriptlets "bounded to scriptlet-ABPF
sandbox semantics, i.e. no page access, per adblock-rust's own model".
The P11 brief sharpens that into a proof obligation: ship ONLY what the
pinned adblock-rust genuinely sandboxes, and refuse everything else with
a typed reason. At the time of writing, what the 0.13.3 pin's sandbox
actually forbids has NOT been verified from a live read (research item
R9b is owed, T6) — and the brief's own honesty law forbids asserting
that from memory. Meanwhile uBO's scriptlet surface has an XSS-shaped
public history, P11 lands before any renderer exists (there is no
injection target), and the list channel is already modeled as a
compromise-equals-remote-behavior-control threat (T10). Scriptlets would
upgrade that to compromise-equals-script-execution-in-every-matching-page.

The brief anticipates exactly this disagreement ("the plan's 'superset'
phrasing vs what is safe at the pin is a disagreement — resolve it in
writing, don't silently under-deliver"). This ADR is that writing.

## Decision

1. **v1 executes no list-derived logic of any kind.** Scriptlets
   (`#%#`, `#$#`, `##+js(`), procedural cosmetic (`#?#`, `#@?#`,
   `:has(`-class operators), regex filters, `$replace`, `$csp`, and
   every filter option other than `$domain=`/`$redirect=` are TYPED
   REFUSALS at compile time, recorded in the bundle's refusal table
   (`{directive, reason, count}`) — never silently ignored.
2. **The refusal surface is measurable and visible**: a closed reason
   vocabulary pinned by `tools/list_bundle_check.py`, per-class compile
   vectors (≥30-case refusal table floor — 47 landed), the counts
   exposed on `xr://shield` (T6) and as `kUnsupportedDirective`
   BlockEvents (T5).
3. **`$redirect=<name>` is the only resource-replace form**, carried as
   a resource NAME (data). The FFI shim passes names, never executable
   bytes, and its cargo features exclude `css-validation` and
   `content-blocking` at the pin.
4. **Simple cosmetic selectors ride along as inert data**
   (`kind:cosmetic`) so bundle formats do not lose upstream information;
   the v1 network engine never matches them and nothing injects them.
5. **Re-opening scriptlets is a human decision** gated on the five
   proofs listed in `docs/shield/scriptlets.md` (cited sandbox read at
   the pin, public bypass advisories, threat-model escalation, both-
   binding parity+fuzz coverage, ADR amendment).

## Alternatives considered

- **Ship the plan's "superset" now** (enable adblock-rust's scriptlet/
  resource machinery at the pin): rejected — the sandbox's prohibitions
  are unverified at the pin (R9b owed), there is no renderer to serve,
  and the failure mode of being wrong is page-privileged script
  execution from a data channel. This is the "silently under-deliver vs
  unsafe over-deliver" fork the brief flags; refusing with typed,
  counted, visible reasons is neither silent nor unsafe.
- **Carry scriptlets as inert data** (like cosmetic selectors): rejected
  — an inert scriptlet in the bundle is a loaded gun for the first
  future engine that "just enables" it; the refusal table keeps the
  capability boundary in the DATA ITSELF, where the digest binds it.
- **Silently drop unsupported directives**: rejected by the brief
  outright ("never a silent ignore") — the refusal counts are how users
  and engineers see what the boundary costs.

## Consequences

- Upstream lists that lean on scriptlets (uBO-filter syntax) lose those
  lines with a recorded reason; coverage regressions attributable to the
  boundary are measurable from the refusal table (and T8's parity corpus
  will quantify the agreement band on the vendored corpus).
- `docs/shield/scriptlets.md` is the standing reference for the
  boundary; R9b (T6) owes the cited sandbox read; T5 owes the
  `kUnsupportedDirective` event path; T6 owes the `xr://shield`
  exposure of the counts.
- If the humans ratify a superset later, it lands behind the five
  proofs — not by loosening `compile.py`.
