# Contract: Update manifest — Omaha protocol 3.1 JSON profile (§1.11 #12)

- **Version:** 1. **Migration note:** `xr-schema-v1.md`.
- **Schema:** `update-manifest-31.schema.json` (strict subset).
- **Example:** `fakes/fixtures/update-manifest-example.json`.

## Source of record (VERIFIED at pin)

Fetched at chromium `d04cdb24d67b081f6cf80200ffc5233f44b61109`:
`docs/updater/protocol_3_1.md` (sha256 `d838a85956fe350330bff25313b0e93ea00b305daa371e53c11c23a904eed3f4`, local copy
`research/protocol_3_1.md`). This is the **Omaha protocol 3.1**. Our profile is
a **strict subset of the update-check RESPONSE** the in-tree client consumes.

## Conformance notes (file:line @ pin)

| our field | 3.1 spec element | spec file:line @ d04cdb24 |
|-----------|------------------|---------------------------|
| response body prefix `)]}'\n` | Safe JSON Prefixes | protocol_3_1.md:194-197, 541-544 |
| `response.protocol == "3.1"` | response object | protocol_3_1.md:546-557 |
| `response.app[].appid` (required) | app (response) | protocol_3_1.md:609-640 |
| `response.app[].status` enum | app status | protocol_3_1.md:626-640 |
| `updatecheck.status` enum (ok/noupdate/error-*) | updatecheck | protocol_3_1.md:658-692 |
| `manifest.version` (required when serving) | manifest | protocol_3_1.md:693-705 |
| `packages.package[].{name,size,hash_sha256,fp}` | package | protocol_3_1.md:714-735 |
| differential `namediff/sizediff/hashdiff_sha256` | package (delta) | protocol_3_1.md:714-735 |
| `urls.url[].codebase` XOR `codebasediff` | url | protocol_3_1.md:747-757 |
| `daystart.elapsed_days` | daystart | protocol_3_1.md:559-566 |

Ordered-URL fallback on 4xx/5xx or hash/size mismatch is spec-mandated
(protocol_3_1.md:736-746).

## Profile scope

We serve single-package CRX updates; `status ∈ {ok, noupdate, error-*}`.
Client **acceptance of our concrete manifest bytes** is a live/farm check
(P10): rows depending on a running client are marked `PENDING-VERIFY-farm`.
The field-set conformance above is verifiable now and is re-asserted in the
test header of `docs/contracts/tests/test_update_manifest_conformance.py`.
