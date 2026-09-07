# Research log — P5 (Contract Freeze)

Pin: chromium_rev `d04cdb24d67b081f6cf80200ffc5233f44b61109` (152.0.7977.82).
All gitiles citations fetched via `?format=TEXT` (base64) at that rev on
2026-09-07. `file:line` refers to the fetched blob at the pin.
UNVERIFIED rows are marked; nothing here is written from memory.

## R1 — `//chrome/updater` protocol 3.1 JSON (VERIFIED at pin)

Source: `docs/updater/protocol_3_1.md` @ `d04cdb24…` (967 lines, sha in
`docs/contracts/update-manifest-31-json.md` header). This is the Omaha
protocol 3.1. Our Update-manifest profile is conformant to the **update-check
response** subset the in-tree client consumes.

Field set consumed by our profile (file:line at pin):
- Safe-JSON prefix `)]}'\n` — protocol_3_1.md:194-197 (§ "Safe JSON Prefixes")
  and reasserted for the response body at protocol_3_1.md:541-544.
- `response` object — :546-557 (`app[]`, `daystart`, `systemrequirements`,
  `protocol` MUST be "3.1", `server`).
- `response.app` object — :609-640 (`appid` MUST, `status` enum: ok /
  restricted / error-unknownApplication / error-invalidAppId; `updatecheck`).
- `updatecheck` object — :658-692 (`status` enum: ok / noupdate /
  error-internal / error-hash / error-osnotsupported / error-hwnotsupported /
  error-unsupportedprotocol; `manifest`+`urls` present iff status==ok;
  `action[]`, `info`).
- `manifest` object — :693-705 (`version` MUST when serving, `packages`,
  `run`, `arguments`).
- `packages`/`package` — :706-735 (`name`, `size`, `hash_sha256`,
  `fp`, differential `namediff`/`sizediff`/`hashdiff_sha256`).
- `urls`/`url` — :736-757 (`codebase` XOR `codebasediff`; ordered fallback;
  4xx/5xx or hash/size mismatch ⇒ fall back to next URL).
- `daystart.elapsed_days` — :559-566.

Conformance stance: our profile is a **strict subset** of the response
schema (we serve only single-package CRX updates, `status ∈ {ok, noupdate,
error-*}`). Client *acceptance* of our concrete manifest bytes is a farm/live
check (P10) → `PENDING-VERIFY-farm` on those rows; the field-set conformance
is verifiable now against the fetched spec and is cited line-by-line in
`docs/contracts/update-manifest-31-json.md` and the test header of
`docs/contracts/tests/test_update_manifest_conformance.py`.

## R2 — mojom IDL grammar / conventions (VERIFIED at pin)

Sources at pin:
- `mojo/public/mojom/base/token.mojom` — `module mojo_base.mojom;`, the
  `[Stable]` struct attribute, plain scalar fields (`uint64 high; uint64 low;`).
- `services/network/public/mojom/network_context.mojom` — real-world
  `struct`/`interface`/`enum` usage; `[MinVersion=N]` field/param versioning;
  large structs with `//`-comment field docs.

Conventions adopted (documented in `docs/contracts/INDEX.md` "Conventions"):
1. **Versioning:** mojom has NO inline file-version field. Chromium versions
   at the *symbol* level with `[MinVersion=N]` on added params/fields/enum
   values, and marks wire-stable types `[Stable]`. XR adds a **file-level
   `const int32 kContractVersion = 1;`** as the human/CI-visible contract
   version (this is the P5 freeze unit), and reserves `[MinVersion=N]` for the
   future in-place additions an approved RFC (T10) authorizes. Both coexist:
   kContractVersion is the freeze/migration anchor; `[MinVersion]` is the wire
   mechanism. Rationale + citation in INDEX.
2. **Typed errors only:** result unions / dedicated `enum *Error` returns; no
   `string message`+`int code` pairs. (Pattern mirrors upstream union results.)
3. **No `any`:** mojom has no `any`; `handle<data_stream>` requires a purpose
   comment (lint-enforced).
4. **Budget comments:** every batch/streamed method carries a `// budget:`
   comment (64 KB Observatory chunk per Plan perf line).

## R3 — §1.11 ↔ P5-T1 file/interface reconciliation (VERIFIED against plan v2)

§1.11 names *interfaces* (`xr.mojom.PolicyResolver`); T1 names *files*
(`policy_resolver.mojom`). Mapping table is the seed of
`docs/contracts/INDEX.md`. Where they diverge, the **file carries the interface
with the §1.11 name** (e.g. file `identity.mojom` → interface `IdentityManager`).
No third name is invented. All interfaces live in `module xr.mojom;`.

## R4 — Signed-bundle envelope for the list-bundle manifest (VERIFIED tool present)

minisign is already the P2/P3 scaffold signer (`build/signing/`,
`build/skip_policy.py` SKIP row). The list-bundle envelope is a JSON manifest
+ **minisign detached signature** over the canonical (sorted-key) bytes, with a
`key_pin[]` allowlist of trusted public keys. Precedent: TUF/sigstore
"sign the metadata, pin the keys" pattern; we use minisign (Ed25519) because it
is already CI-installed and its detached-signature format is simple and
already skip-gated. "Compromise ⇒ T10 remote-behavior-control" threat row is
cited in the doc; delta rules define fail-closed-to-last-known-good.

## R5 — settings/theme/command formats (peers, for compat)

- Chromium prefs versioning: `components/prefs/` uses a monotonically-increasing
  integer schema/version stored with the data; migrations are forward-only.
  We mirror this in `xr-schema-v1` ({version, created_at} on every row;
  forward-only chain). (Peer *pattern* cited; not a byte-for-byte port.)
- Theme = **declarative JSON only (R13)** — no JS, enforced by
  `theme-tokens-v1` (token names + types; no code fields).
- Command descriptors satisfy §10 Attention Budget tiers + "every feature
  without a command does not ship" (danger-class required on every command).

## R6 — golden-vector discipline (WPT-style)

Expectation files are hand-authored JSON tables (like WPT `*-expected.txt`),
one input→output row each, byte-stable (sorted keys, no timestamps) so P9 can
diff. `vectors/` holds `policy-resolver-v1.json` (≥64) and
`route-manager-v1.json`. Runner `tools/vectors_check.py` compares fake output
to the vectors byte-for-byte.

## R7 — §9.8 lint + §11.15 evidence house rules (re-read)

New tools match house style: stdlib-only, `--help`, `--json`, exit {0,1,2},
<400 LOC, fail-closed, never a silent pass (SKIP policy for absent externals).
Evidence bundle conforms to `docs/contracts/evidence-bundle-v1.md` and passes
`tools/evidence_check.py --strict`.

## UNVERIFIED / BLOCKED
- Real mojom parse/compile (GN bindings) — needs the pinned checkout +
  toolchain (HG-9/HG-27). Our `mojom_lint.py` is a **structural** parser, not
  the real one (stated). → BLOCKED-TOOLING.
- Updater *client acceptance* of our concrete manifest bytes → farm (P10),
  `PENDING-VERIFY-farm`.
- Legal review of Isolation-Card strings → HG-1.
