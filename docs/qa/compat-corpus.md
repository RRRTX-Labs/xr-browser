# Compat corpus & Beta-parity (P9-T4) — provenance and the live-mode law

Owner tools: `tools/compat.py` (corpus validate/replay/live), `tools/wpt_delta.py`
(WPT delta bot) · Workflow: `.github/workflows/compat-beta-parity.yml`.

## Corpus (data, `xr-core/test/corpus/corpus.yaml`)

Entries carry a URL **class**, never a live URL — no scraping and no
live-site dependency in this phase (failure condition 4). Each entry =
{url class, flow steps as data, expectations, owner, provenance}. Three
modes:

| Mode | What runs | Where |
|---|---|---|
| `validate` | schema + fixture presence + known expectation keys | here (real) |
| `replay` | offline fixture exercises its flow class (login fixture without a password field = fail) | here (real) |
| `live` | **refused** unless `XR_LIVE_NET=1` **and** the host is on `build/upstream/fetch.py`'s allowlist | farm (HG-31) |

**Live-mode law (L10-ish):** corpus contents are reviewed before any live
fetch. This repo adds **no** hosts to the fetch allowlist for the corpus; if
a real live-fetch need ever arises, that is a stop-and-report, not a
config edit. The runner enforces this in code (never prose).

## Corpus size honesty (DoD 6)

The plan's 500+200+50 set is authored progressively. This phase ships 20
representative entries (10 top-500 classes, 5 regional, 5 hard-app) — each
with a real offline fixture. The remaining entries are owned by P36
(hard-app scripts) and P38 (corpus freshness); padding entries that test
nothing are worse than a missing one, so none were padded.

## WPT delta bot

`tools/wpt_delta.py` compares two result sets and enforces the §11.12 law as
data: delta ≤ 0.5% is `WITHIN-TOLERANCE`, above is `REGRESSION` (exit 1).
The flaky rule is recorded, not hand-picked: a baseline `FLAKY` test is
excluded by the comparator's own rule. Committed synthetic sets
(`docs/qa/wpt-fixtures/`) pin the 0.5% boundary (5/1020 = 0.490% within;
6/1020 = 0.588% regression).

## Workflow

`.github/workflows/compat-beta-parity.yml` — schedule + `workflow_dispatch`
(with the nightly's spurious-push `if:` guard), never pushes (L24). Steps
are real where possible (validate + replay + synthetic delta), SKIP-visible
where a browser is required. Artifact uploaded for the promotion gate.
