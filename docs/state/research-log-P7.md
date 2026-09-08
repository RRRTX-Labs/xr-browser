# Research log — P7 (one command registry, four views, window chrome)

The P7 working notes: what was decided, what was found, and why. This doubles as
the review packet for the new `command-host-protocol v1` contract registered in
`docs/contracts/registry-post-freeze.md` (P6-T5 pattern).

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
