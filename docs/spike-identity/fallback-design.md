# Fallback design — identity = BrowserContext (Plan P4-T9)

**Status:** design only. **No code in this document.** It exists so that if
P4's runtime probes falsify the partition seam, the re-cut is executed from a
documented plan instead of improvised under pressure (the Plan's own words:
*"if falsified: execute … documented, not improvised"*).

**Triggers:** ADR-0042 falsification triggers **F1, F2 or F3**. F4–F7 do not
trigger this fallback — they are scoped workstreams, not a model change.

## The fallback model

Identity becomes a **`BrowserContext`** (in Chrome terms: a `Profile`, created
the way an off-the-record profile is), instead of a `StoragePartitionConfig`
domain inside one Profile.

| dimension | partition model (primary) | BrowserContext model (fallback) |
|---|---|---|
| isolation unit | StoragePartition inside one Profile | whole Profile |
| renderer non-sharing | guaranteed by upstream `CHECK`s | guaranteed by upstream (`host->GetBrowserContext() != browser_context` ⇒ not suitable) |
| storage isolation | partition-scoped | complete, by construction |
| Profile-shared surfaces (§1.4.5) | **shared** — 9 S1 papercuts | **not shared** — the census mostly dissolves |
| network binding | `ConfigureNetworkContextParams` per partition | per-Profile NetworkContext (same hook, one level up) |
| window-per-identity | not required | **required** |
| extensions | one registry is a cross-identity oracle | per-Profile registry |
| cost | ~25 files (P5) | higher UI cost, lower isolation cost |

## What the re-cut does to the P14 registry rows

Enumerated from `docs/registry/features.yaml` (generated from the pinned plan)
— every row whose `phase_tokens` include `P14`. These are the rows a
successor-commit must re-cut; nothing here is hand-waved.

| registry id | feature (truncated at 60 chars) | phases | owner | crit | tier | impact of the fallback |
|---|---|---|---|---|---|---|
| F-022 | Identity (the moat) = StoragePartitionConfig seam + overlay | P14 | B | P0 | S0 | **Directly contradicted.** The feature text names the partition seam; it must be amended through `docs/process/plan-amendment.md` + re-pin, or re-implemented on BrowserContext. S0 ⇒ dual review either way. |
| F-023 | Identity templates (Personal/Work/Research/Banking/Shopping/…) | P14 | B | P0 | S1 | Implementation changes (a template becomes a Profile), behaviour does not. |
| F-026 | Disposable (ephemeral) identities — plural, simultaneous, in… | P14 | B | P0 | S0 | **Harder.** Ephemeral ⇒ OTR Profile; "plural, simultaneous" means many OTR Profiles alive at once, each with its own process set. Memory cost is the real question. |
| F-027 | Mixed identities in one window | P14(v1)/P34(split) | B | P0 | S0 | **The main casualty.** BrowserContext-per-identity cannot put two identities in one window without embedding, so this either moves out of v1 or needs a window-per-identity UI with an aggregator. |
| F-031 | Profiles (OS-persona) | P14 | B | P1 | — | **Collision.** "Profiles" and "identities" become the same primitive; the product must decide whether XR Profiles are exposed at all, or merged into identities. |
| F-032 | Adaptive Trust = one resolver; dial Standard/Shield/Fortress | P14 | B | P0 | S0 | Unchanged in intent; Fortress (OTR) becomes the *default shape* of every identity rather than a special case. |

## Cost analysis

**Window-per-context UX.** A `BrowserContext` maps to a browser window in
Chrome's UI model. Identity-per-window means:

* N identities open ⇒ N windows, each with its own tab strip. Mixed-identity
  windows (F-027) are no longer expressible in v1.
* Tab **search** (`C-11`) is naturally scoped to a window here, which removes
  an S1 leak — but only at the cost of cross-identity tab search becoming a
  cross-window, cross-process feature (a new design, not a papercut).
* The command palette must become window-aware and then be re-unified across
  windows; that is ~8 files × `ui` of new work that the partition model does
  not need.
* Drag-and-drop of a tab between identity windows (`C-05`, `C-13`) is a
  cross-context move: it is a *tab move* in the partition model and a
  *context migration* here, with a destructive reload either way.

**Estimates (files × §1.2 category).**

| workstream | partition model | BrowserContext model |
|---|---|---|
| core isolation | 6 × `hook_points` | 14 × `hook_points` + 6 × `ui` |
| Profile-shared surfaces (C-01/04/10/11) | 23 × `ui` + 7 × `hook_points` | ~4 × `ui` (mostly dissolves) |
| window/tab-search/palette | 0 | ~20 × `ui` |
| ephemeral (F-026) | 4 × `hook_points` | 9 × `hook_points` + 5 × `ui` |
| **total** | **~40 files** | **~58 files**, but ~19 fewer S1 papercuts |

So the fallback is **cheaper on isolation correctness and more expensive on
UX**. It is the right call if and only if F1/F2/F3 fire.

## Decision triggers (verbatim from Plan P4-T9)

> *"if falsified: execute … documented, not improvised"*

Concretely, the sequence when a trigger fires:

1. Stop all runtime-pending claims. Update ADR-0042 status to
   `SUPERSEDED-BY-ADR-NNNN` (a new number; 0042 is never reused).
2. File a draft issue with the failing probe output and the citations.
3. Re-cut the six P14 rows above through `docs/process/plan-amendment.md`
   (plan amendment + re-pin in one commit) — F-022's S0 status means dual
   review on the amendment.
4. P5's identity-adjacent contract freeze does **not** proceed (HG-24).
5. Only then write code.

## What the fallback does NOT solve

* DNS/`HostResolverManager` sharing (S-16/S-17) is NetworkService-wide and
  survives a BrowserContext split.
* The GPU process and the clipboard stay shared (P-8/P-9).
* Extensions: per-Profile registries help, but the DevTools target registry
  (C-03) is browser-wide and still needs its own fix.
