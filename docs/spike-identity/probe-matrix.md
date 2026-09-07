# Probe matrix — spike probe ↔ adversary ↔ future isolation-matrix row (§11.4 seed)

The Plan says the P4 probe scripts *graduate into* the §11.4 isolation matrix.
This file is the join between them: every probe names the adversary it is
answering, the threat-model row it feeds, and the iso-matrix row id it will
occupy. Result rows are emitted in the
`docs/contracts/spike-result-v1.md` shape so today's output and P14's matrix
rows are the same record type.

| probe | source | adversary it answers (threat model) | iso-matrix row (§11.4) | expectation | today |
|-------|--------|--------------------------------------|------------------------|-------------|-------|
| `probes/isolation_matrix_browsertest.cc::PartitionsAreDistinct` | runtime | T2 (cross-identity tracker) | ISO-01 | two identities ⇒ two non-default partition domains | PENDING-FARM |
| `…::StorageBackendsAreDistinct` | runtime | T2 | ISO-02 | distinct StoragePartition objects and paths | PENDING-FARM |
| `…::SameSiteDifferentPartition` | runtime | T2 | ISO-03 | same site + different identity ⇒ different partition (the row the embedder override cannot satisfy, S-01) | PENDING-FARM |
| `probes/process_sharing_browsertest.cc::IsolationIsEnabled` | runtime | — (self-check) | ISO-00 | no isolation-bypass flag is present; a run without isolation is no evidence | PENDING-FARM |
| `…::SameSiteDifferentIdentitySeparateBrowsingInstances` | runtime | T5 (malicious site) | ISO-04 | never a shared BrowsingInstance across identities | PENDING-FARM |
| `…::PartitionSurvivesCrossSite` | runtime | T5 | ISO-05 | cross-site navigation stays in the identity partition | PENDING-FARM |
| `probes/network_context_browsertest.cc::DistinctNetworkContextsPerIdentity` | runtime | T3 (network observer) | ISO-06 | one NetworkContext per identity | PENDING-FARM |
| `…::EphemeralHasNoDiskPath` | runtime | T4 (local forensic) | ISO-07 | ephemeral ⇒ empty path ⇒ no files | PENDING-FARM |
| `…::DnsResolverScopeIsDocumented` | runtime | T3 | ISO-08 | documents the shared HostResolverManager rather than claiming isolation | PENDING-FARM |
| `probes/ephemeral_zero_write_browsertest.cc::EphemeralPartitionIsInMemory` | runtime | T4 | ISO-09 | `in_memory == true`, zero files under the partition path | PENDING-FARM |
| `…::OtrForcesInMemory` | runtime | T4 | ISO-10 | OTR forces in-memory (Fortress) | PENDING-FARM |
| `probes/fortress_profile_coexist_browsertest.cc::OtrCoexistsWithDomains` | runtime | T4 | ISO-11 | custom domains + OTR coexist, forced in-memory | PENDING-FARM |
| `…::OtrIdentitiesStaySeparate` | runtime | T4 | ISO-12 | OTR identities do not collapse | PENDING-FARM |
| `…::OriginalAndOtrDoNotCollapse` | runtime | T4 | ISO-13 | original profile and OTR never share a partition | PENDING-FARM |
| `build/spike/genpatch.py` round-trip | static | — | ISO-BUILD-01 | the hook patch applies/verifies/reverts at the pin | **VERIFIED** (see evidence/P4/logs/genpatch-roundtrip.txt) |
| `build/spike/citation_audit.py` | static | — | ISO-BUILD-02 | every cited `file:line` still says what we claim | **VERIFIED** (23/23) |
| `build/spike/probe_driver.py --offline` | static+fixture | — | ISO-BUILD-03 | driver, parsers and policy lints run without a browser | **VERIFIED** |
| `build/spike/fsdiff.py` | fixture | T4 | ISO-BUILD-04 | FS-diff detects any added/removed/changed path | **VERIFIED** (synthetic trees) |

## Adversary mapping (threat model rows fed by these probes)

| adversary | what it wants | probes that constrain it | known residual |
|-----------|---------------|--------------------------|----------------|
| T2 tracker | link activity across identities | ISO-01..03 | Profile-level history/omnibox/autofill (TM-P4-4/5) |
| T3 network observer | link traffic to one identity | ISO-06, ISO-08 | DNS manager + OS resolver cache (TM-P4-8) |
| T4 local forensic | recover ephemeral identity data | ISO-07, ISO-09..13 | GPU process, clipboard (TM-P4-9) |
| T5 malicious site | escape into another identity's storage | ISO-04, ISO-05 | extension messaging (TM-P4-7) |
