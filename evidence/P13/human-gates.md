# P13 human gates

Acts this sandbox cannot perform, recorded so nobody mistakes absence for
completion. Each row names what would be needed and what the honest fallback is.
`HG-33` is P13's own new row; the rest are the standing gates the brief lists.

| id | gate | why the agent cannot close it | what stands in for it |
|---|---|---|---|
| HG-20 | Revoke (or keep) the PAT supplied for this dispatch | Credential lifetime is a user action; the brief records that the P12/P13 PAT is still unrevoked | Nothing — the agent never touches it, never echoes it, and the token is absent from both trees (`tools/secret_scan.py --all` = PASS over 3198 files) |
| HG-26 | Ratify-or-amend the 14 `PENDING` rows in `docs/contracts/FROZEN.yaml` | Freezing a contract is a human amendment | `breakage-report-v1` and `panel-tab-registration-v1` land LIVING + registered in `docs/contracts/registry-post-freeze.md`, with ADRs as **proposals** (approval is the human act); `FROZEN.yaml` bytes untouched (`0b79e43988f31df45d60d0c228d4e2693cc01fcfd1d38e4d0376741a03da01a1`) |
| HG-34 | Branch protection on both repos | Org settings; both repos still accept direct pushes to `main` — which is exactly why "red at HEAD" is possible at all | The push gate itself: `governance` + `core-hardening` must be green at the recorded head, cited as `ci-run` rows (`tools/evidence_finality.py`, `tools/evidence_ci.py`) |
| HG-28 | 24 h full-mutation matrices and real-rig perf `MET` assertions | Needs a real rig and a day of wall-clock, neither of which exists here | Mutation freshness for every touched core with survivors dispositioned; perf rows generator-owned, `rig_class: trend`, never `MET` on this host (`build/qa/perf/perf_budgets.py --check`) |
| HG-31 / HG-9 / HG-27 | Browser rig, real mojom bindings, rendered-panel screenshots | No Chromium checkout, no `gn`/`ninja`, no browser in this sandbox | Every rendered/browser claim is `NOT-RUN (method: docs/qa/browser-harness.md)`; the panel's DOM-level tests run under the repo's own harness |
| HG-33 | Filing real breakage reports into the public queue | Publishing to a third-party queue is an attributable human act (and the live queue is not reachable from here) | The local fixture queue, labelled `fixture` in its path *and* in the tool's stdout; the live half stays `HUMAN-GATED`/`NOT-RUN` with a written drill (`docs/panel/breakage-report.md`) |
| HG-32 | Upstream-first ledger entries for anything P13 diverges on | Requires filing upstream; never invent an issue URL | Divergences are recorded as proposals in the ledger with the upstream path named and no URL fabricated (`docs/state/research-log-P13.md`) |
| HG-35 | Approving the panel-tab-registration and breakage-report ADRs | ADR approval is a human act even when the implementation is done | ADRs ship as **proposals** with their implementation and tests attached |
