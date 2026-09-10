# Contract: leaktest result v1 (`build/qa/leaktest/leaktest-result.json`)

**Status:** active (post-freeze registry) · **Introduced:** P9-T3 ·
**Validator:** `tools/leaktest.py` (the runner) + `tools/evidence_check.py`
(citations) · **Owner:** A lead (Platform/Chromium) — privacy track.

## Why a contract

The endpoint audit (§11.8) is a release blocker: "set of contacted hosts must
equal the documented set exactly". Without a machine-readable result format,
that claim is prose. This schema is what the farm's capture lane and the
sandbox's loopback lane both emit, so a leak is a JSON diff, not an argument.

## Schema (v1)

```json
{
  "as_of": "ISO-8601 (frozen clock)",
  "mode": "loopback | capture",
  "rig_class": "trend | reference | farm",
  "cells": 30,
  "leak_count": 0,
  "ok": true,
  "results": [
    {
      "probe": "dns-egress",
      "state": "fresh-profile | after-import | after-toggle",
      "observed": ["host[:port]"],
      "documented": ["host[:port]"],
      "leaks": ["host[:port]"],
      "verdict": "CLEAN | LEAK"
    }
  ]
}
```

## Laws

1. `observed ⊆ documented`, exactly. The documented set for a probe lives in
   `build/qa/leaktest/probes.yaml` and grows **only** in the same commit as
   the feature that documents the contact (never a silent append).
2. The empty-run law applies: `cells` must be ≥ the number of probes (a
   runner that executed zero cells is a failure, not a pass).
3. Self-verification is mandatory: `tools/leaktest.py --self-test` must prove
   the harness detects a planted egress, and must exit non-zero when a
   planted egress goes undetected (a blind harness is the bug class this
   phase exists to eliminate).
4. `rig_class` is part of the verdict: only `reference` rigs may assert
   product compliance; `trend` (this sandbox class) records numbers for
   regression shape only (docs/hw.md).

## Registered

Post-freeze registry entry in `docs/contracts/registry-post-freeze.md`
(P9 section). No frozen contract is redefined by this schema.
