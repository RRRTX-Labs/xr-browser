# ledger-identity-overlay-v1 (LIVING, post-freeze)

**Phase:** P14-T5, delivered by P14-CLOSE C-2. **Status:** LIVING. It is registered in
`docs/contracts/registry-post-freeze.md` and is not ratified (HG-26).
`FROZEN.yaml` is byte-identical.

Plan §4 P14 T5: "history/bookmarks identity tagging via ledger overlay
(upstream history untouched; omnibox results filterable)". Contracts-out:
"ledger identity_id everywhere".

## What it is

The overlay is a wrapping record. It puts one **required** `identity_id` on a ledger event of any
class. The wrapped event keeps its own contract, and its bytes are carried unchanged
(canonical JSON, sorted keys). Those contracts are `block-event-v1`, `policy-change-event-v1`,
`permission-audit-event-v1` and the frozen `ActivityRow` export. None of their
schemas are edited. The amendment record is in `registry-post-freeze.md` §P14-CLOSE C-2.

| Field | Type | Law |
|---|---|---|
| `schema` | string | exactly `ledger-identity-overlay-v1` |
| `identity_id` | string | **REQUIRED**. It must be mint-shaped: `xr:` followed by a v4-shaped UUID, the same `DomainShapeOk` the identity core uses. There is no default and no optional form. |
| `event_class` | string | Closed set of ten: the eight frozen `ActivityKind` values (`xr-core/mojom/activity_log.mojom`, read live by the gate) plus `kHistory` and `kBookmark`. |
| `event` | object | The wrapped event, carried byte-for-byte. |

## The five laws

* **L1 — identity required.** Tagging refuses a missing or empty id with `identity-id-required`. It refuses a
  non-mint-shaped id, such as a display name, with `identity-id-malformed`. Both are typed
  `kRejected` refusals with exit 0. The refusal never echoes the offered value.
* **L2 — closed classes.** An unknown class is refused with `unknown-event-class:<cls>`.
* **L3 — event is an object.** Anything else is refused with `event-not-object`.
* **L4 — omnibox filtering.** `omnibox-filter` returns three things:
  * `current`: only the current identity's rows.
  * `unknown`: rows with a missing or invalid id. These are re-typed `provenance:"unknown"` with
    `identity_id` removed. They are never attributed to the current identity.
  * Rows of other identities are dropped. They are not counted, so no count leaks another identity's activity.

  A request without a current identity is refused, not answered with all rows.
* **L5 — upstream untouched.** The overlay is a side table keyed by
  `url_id`/`visit_id`. `history-oracle` canonicalises the upstream rows before
  and after the overlay pass. It answers `diff-clean` only when they are byte-identical to
  each other and to the input. Any write into upstream rows gives `DELTA`. An upstream
  row carrying a field outside `url_id, visit_id, url, title, ts`, such as an
  `identity_id` column, is refused with `upstream-row-unknown-field:<k>`.

## Backends (byte-identical)

* C++: `xr-core/identity/core/ledger_tag.{h,cc}`, reached through `identity_host`
  LIVING subcommands `ledger-tag`, `omnibox-filter` and `history-oracle`
  (`xr-core/identity/host_protocol.md`). The unit lane is
  `identity/tests/test_ledger_tag.cc`.
* Python twin: `xr-core/fakes/ledger_identity.py`. It uses the same CLI shape and the same
  canonical bytes, including `\uXXXX` escapes and surrogate pairs for non-ASCII.
* Golden: `docs/contracts/vectors/ledger-identity-overlay-v1.json`. Every class
  has a tagging vector and a missing-identity refusal vector.

## Gate and negatives

`tools/ledger_identity_check.py` replays every vector against both backends and checks that the
stdout bytes and exit code are equal. It also checks:
* per-class coverage;
* the schema of every successful record (`tools/xr_schema.py` contract `ledger-identity-overlay`);
* drift of the frozen `ActivityKind` set;
* the oracle, which prints `history-oracle: upstream history diff-clean (N vectors)`.

Without g++/make, the C++ half SKIPs visibly (exit 77). The Python half still runs.

The negatives are in `tools/negatives/p14c_c2.sh`. The gate has no plant flags. Each plant is an
exact-anchor replacement made in a per-case `mktemp -d` scratch copy, and the gate is pointed at the
planted twin with `--twin PATH` (C++ half skipped for that run). Each one must redden:
* Omnibox leak: the twin's omnibox filter ignores identity, so a cross-identity row reaches
  `current` and the replay FAILS.
* Upstream write: the twin writes `identity_id` into upstream history rows, so the oracle answers
  `DELTA` and the replay FAILS.
* Laws: a coverage hole, a record without `identity_id`, a frozen `ActivityKind` drift and a
  hand-edited vector each produce a named FAIL. The negative imports the gate and calls `laws()`.
* C++ leak: a planted leak in a scratch copy of `ledger_tag.cc` reddens `test_ledger_tag`. It SKIPs
  visibly without g++/make.

## Review

There is no wire-format change to any frozen or living contract. What a reviewer reads:
* the closed class set against `activity_log.mojom`;
* the refusal strings in L1–L3 never echo input (pinned by `test_derivation.cc`
  `TestOverlayRefusalsCarryNoInput`);
* the L4 drop-not-count rule.

Freezing this contract is a human act (HG-26). Its stamp condition is met when the browser-side history
and omnibox consumers exist and read the overlay. That happens only on the farm (HG-31), so until then the
contract stays LIVING.
