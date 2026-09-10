# Rig classes & the budget-assertion law (P9-T5)

The plan's law (restated): **budgets are asserted by rigs of a named class;
a number measured on the wrong class is recorded, never asserted.** This file
defines the classes and the exact rule the comparator (`tools/perf_gate.py`)
encodes.

## The three rig classes

| class | definition | may print `MET`/`MISSED` on |
|---|---|---|
| `reference` | named hardware, thermal-locked, camera'd (the plan's "fixed HW list") | **any** budget row — the only class that may assert a browser-side budget |
| `trend` | this sandbox class: 2 CPUs, ~2 GiB RAM, no browser | **core-side** rows only (numbers are compared for regression *shape* on browser-side rows, never asserted as product compliance) |
| `farm` | browser/E2E/visual runners (HG-31) | nothing (they feed captures/snapshots, not budget verdicts) |

## The encoded law

1. A budget row carries a `surface` (`core-side` | `browser-side`) and an
   `assert_class` (the least-privileged rig class allowed to emit
   `MET`/`MISSED` on it).
2. Rank: `trend` (1) < `reference` (2). A rig may assert a row iff its class
   rank ≥ the row's `assert_class` rank.
3. **Consequence (the negative fixture):** a `trend` rig emitting `MET` on a
   `browser-side` row is REFUSED by the comparator (exit 1), not downgraded.
4. Noise law: a delta inside the ±2% noise band is `NEUTRAL` (recorded for
   trend shape), never `MET` — and a delta beyond it is `MISSED` (regression,
   auto-assigned via the S0 owner map).

## This sandbox (a `trend`-class example)

```
nproc:   2
Mem:     ~1.9 GiB total
CPU:     Intel(R) Xeon(R) Processor @ 2.60GHz (sandbox vCPU)
arch:    x86_64 Linux
```

Prior phases recorded their hardware line the same way; copy this framing
(never assert browser-side budgets from here — `docs/limitations.md` records
the two-core sandbox caveat for the core-side numbers too).
