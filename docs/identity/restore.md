# Session restore with identities (P14-T8)

Status: the session store and its restore law are pure core, proved by a
seeded chaos suite and an isolation-matrix cell run here. Real session
files and a real `kill -9` are NOT-RUN (method at the bottom).

## The one law: restore never bleeds

The census row C-14 named the failure mode: a restore that falls back to
the default partition silently merges two identities. The session store
(`xr-core/identity/core/session.h`) makes that unrepresentable:

* each tab is restored to **its recorded domain**: never another
  identity's, and never the default partition;
* a tab bound to a domain that is not in the live identity set (a tampered
  or stale session) is **refused** with `kMalformedInput` naming the tab.
  Restore never guesses: a refusal is better than a fallback that merges
  identities;
* **disposables are never restored**. `Snapshot` does not write
  disposable-bound tabs and returns them in `dropped`; `RestoreSession`
  reports dropped tabs. The drop is reported, never silent
  (`docs/identity/disposable.md`).

The session document is `{schema, schema_version: 1, tabs: [{tab_id,
domain, window}]}`, serialized sorted by `tab_id` so the same state always
gives the same bytes. Domains are the opaque identity domains, so a
session file carries no display name. That opacity rests on the seam
decision recorded in `docs/state/research-log-P14.md` §"seam decision".

## Where it is proved

* `xr-core/identity/tests/test_session_chaos.cc`: seeded kill points
  (seeds 20260910, 7, 424242) in the middle of provision, bind, snapshot,
  destroy and restore cycles, interleaved with hibernate, wake and move.
  The restored state must equal the pre-kill state exactly for durable
  identities, with zero residue for disposables.
* Isolation matrix cell `session-restore-no-bleed`: all 5 identity pairs,
  shown on the Isolation Card as `holds` (`docs/limitations.md`, generated
  block).
* Census ledger row C-14 (`docs/spike-identity/papercut-census.md`) is
  `closed-core`, with this suite as its test.

Transcripts: `evidence/P14/logs/t8-identity-suite.txt`,
`evidence/P14/logs/t5-t6-isolation-matrix.txt`.

## NOT-RUN (method, not a surrogate)

Kill each process type with `kill -9` while identities are live, restart,
and assert every tab returns to its own partition
(`XRIdentityTabData::PartitionMatchesLiveSiteInstance()`). This is P9-T11's
drill: `docs/qa/drill.md`, restated in `docs/qa/browser-harness.md`.
