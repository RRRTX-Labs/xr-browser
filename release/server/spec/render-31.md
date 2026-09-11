# render-31.md — the byte-exact 3.1 rendering law (P10-T2, language-neutral)

This file is the CONTRACT both backends implement:
`release/server/refimpl/update_server_ref.py` (reference, Python stdlib)
and `release/server/rust/` (the deployable, std-only Rust, zero crates).
A byte of divergence between the two on the conformance corpus
(`release/server/tests/conformance.json`, ≥40 cases) is a red gate — the
P9 differential-parity lesson applied to the new language boundary.

## Request grammar (closed)

Wire framing: a request body is an optional `)]}'\n` prefix followed by
one JSON object followed by nothing. HTTP `Content-Length`, when present,
must equal the body byte length; a shorter body is `kTruncated`, a longer
one `kBadLength`, either way a canonical error object with HTTP status
400. Bodies above `REQUEST_CAP` (65536 bytes) are `kTooLarge` — refused
before parsing.

After stripping the prefix, the object is closed at every level:

```
{protocol: "3.1",                      // const; anything else kWrongProtocol
 os: {...},                            // parsed, ignored (no transport datum)
 app: [ {appid: string 1..128,         // kBadAppid
         version: "M.m.b.p" canonical, // kBadVersion (non-canonical refused)
         channel: nightly|beta|stable|dev,
         bucket: 0..99,                // kBadBucket (client computes it)
         epoch?: string}, ...] }       // optional: caller's current epoch
```

Unknown field at ANY level ⇒ `kUnknownField`. Malformed JSON ⇒
`kMalformedRequest`. Empty app array ⇒ `kMalformedRequest`.

## Decision order (per app entry)

1. `channel` unserved (`dev`) ⇒ `updatecheck.status = "noupdate"`.
2. `channel` paused ⇒ `updatecheck.status = "error-pausedChannel"`.
3. caller `epoch` ∈ revoked list ⇒ `updatecheck.status = "error-epochRevoked"`.
4. `bucket >= per-channel ramp_percent` ⇒ `"noupdate"` (bucket law:
   in-ramp iff `bucket < ramp_percent`; boundary cases are conformance
   data, never vibes).
5. `parse_version(app.version) >= parse_version(head.version)` ⇒
   `"noupdate"` (equal is a re-offer; newer is impossible-by-law; the
   server never offers a downgrade).
6. otherwise the head manifest renders (below).

## Response rendering (byte law)

A 200 response is exactly:

```
)]}'\n
{canonical envelope}\n
```

where the envelope is canonical JSON — `json.dumps(sort_keys=True,
separators=(",", ":"), ensure_ascii=True)` in the reference; sorted-key,
`,`/`:`-tight, `\uXXXX`-escaped in Rust — of exactly this shape:

```
{epoch:    {epoch_id, key_id, seq},            // from epochs.yaml active
 response: {app: [{appid, status: "ok",
                   updatecheck: {status: "ok",
                     manifest: {version, packages: {package: [{name,
                                size, hash_sha256, fp}]}, run: ""}}},
                  ...],
            daystart: {elapsed_days: 0},       // server holds no per-client state
            protocol: "3.1", server: "pub"},
 schema: "xr-update-envelope", schema_version: 1,
 signature: {alg: "minisign-ed25519", key_id, sig}}
```

`sig` = `stub_sig(key_material, canonical(response))` — the SAME TEST-ONLY
scheme the client test fixture pins (`sig:` + first 16 hex of
`sha256(material + "|" + message)`); production signing is HSM-held and
human-gated (HG-36). Error responses (status 400) are canonical
`{detail, error}` objects — sorted keys, no prefix, no envelope.

`daystart.elapsed_days: 0` always: a **stateless** server (no per-client
counters — release/server/README.md). The log-scrub law: the server logs
NOTHING (release lane prints nothing but the response bytes on stdout).

## Invariants the fuzzers enforce

* Never emit a manifest the verifier would deny for missing/foreign
  signature or epoch (oracle runs the client's own verify over every 200).
* A request handled twice yields byte-identical responses (no state);
  after a revocation lands in epochs.yaml, the response differs.
* Response ≤ 2048 bytes raw on the largest realistic case
  (`tools/server_size_check.py`).
