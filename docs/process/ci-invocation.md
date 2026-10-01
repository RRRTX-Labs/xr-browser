# Running the gate the way CI runs it (P13-P0-A)

**The rule, one line: run the gate the way CI runs it.**

`governance.yml` does not run `bash tools/run_checks.sh`. It runs

```yaml
run: |
  if [ -n "$CHECK_RANGE" ]; then
    tools/run_checks.sh "$CHECK_RANGE"
  else
    tools/run_checks.sh
  fi
```

— a **direct exec** of a repo path, with one positional argv element (a git
range, or *no argument at all* when the push range is empty). A direct exec
consults the file's **mode**; `bash <path>` does not. That difference is not a
style preference: on a runner a non-executable file is

```
Process completed with exit code 126
```

which is the failure that kept this repository's `governance` lane red for three
consecutive commits after `5e3d1d4` flipped `tools/run_checks.sh` and
`tools/run_negatives.sh` to `100644`. Every local run was green throughout,
because every local run used `bash`.

## Use it

```bash
tools/run_checks.sh --via-ci-invocation            # no range: full history, exactly as an empty CHECK_RANGE does
tools/run_checks.sh --via-ci-invocation <base>..HEAD
```

The mode does two things, in order:

1. It refuses to run if the entry point is not executable **in the index**
   (what a runner checks out) or on disk, naming exit 126 and the fix
   (`git update-index --chmod=+x <path>`) instead of producing a bare
   `Permission denied`;
2. it then `exec`s the literal workflow command line — same file, same argv,
   same cwd — so the local run and the hosted step are the same process image.

`bash tools/run_checks.sh --via-ci-invocation` (note the `bash`) is the useful
form while the bit is still wrong: the wrapper reports the mode even when the
interpreter would hide it. That exact shape is a registered negative
(`tools/negatives/p13_p0a.sh`, case `ci_invocation_sees_a_644_entry_point`).

## The laws behind it

* `tools/entrypoint_mode_check.py` — **Law 1**: every `.github/workflows/*.yml`
  `run:` block is parsed, and every command whose first token is a repo path
  executed **directly** must be `100755` in the git index. `bash <path>` /
  `python3 <path>` / `node <path>` invocations are **exempt**, and the tool says
  so in its own output (the interpreter is the executable; the file's mode is
  not load-bearing) — an exemption that is printed is reviewable, one that is
  silent is a hole. **Law 2** (`--range`): no commit in the pushed range may
  change a tracked file's index mode from `100755` to `100644`. Replayed over
  history, Law 2 returns exactly the incident:

  ```
  FAIL (mode drift): 5e3d1d4 (P12-T0-d: moving NEG_TMP into the repo broke four gates…) :
      tools/run_checks.sh lost its executable bit (100755 -> 100644) in this range
  ```

* `tools/inplace.py` — every **in-place rewrite** of an existing file copies the
  pre-write `stat` mode onto its replacement before `os.replace` publishes it
  (`rewrite_in_place`, `rewrite_bytes_in_place`). A new file gets an explicit
  mode, never the umask. `--self-test` proves a `0755` fixture survives a
  rewrite, and `--simulate-naive` proves the *assertion* can fail (the
  write-new-then-replace shape loses the bit — the `5e3d1d4` class, reproduced).

Both laws run in the `governance` gate (`tools/checks/p13_gates.sh`, lane
`p13_p0_gates`), so they are enforced locally, in CI, and at push time.

## The two invocations of the gate: push and phase-close

The same file, two contracts (P13-P0-C):

* **`tools/run_checks.sh [range]`** — the push gate. CI runs exactly this on
  every push to `main`. Evidence bundles are judged **strict**, and the phase
  the tree declares in flight (`docs/state/phase-base.json`) is allowed to be
  `state: "interim"`: a bundle owed from a phase's *first* commit cannot be
  final from its first commit.
* **`tools/run_checks.sh --phase-final`** — the closing gate. The in-flight
  phase must be `final` too (a 12-section `report.md`, a declared `phase_head`,
  and a same-head `ci-run` row per claimed workflow). This is the invocation the
  phase's final commit and the clean-clone gate run recorded in the phase report
  use, so a phase cannot close with a `*-PENDING-*` sentinel still standing —
  the "we forgot to flip the bundle" failure mode, which nothing else catches.
  The flag is parsed in `tools/checks/gate_runner.sh` (`PHASE_FINAL=1`) and
  turned into `--require-phase-final` by `tools/checks/p13_gates.sh`
  (`p13_evidence_bundles`). Registered negatives:
  `tools/negatives/p13_p0c.sh`, cases `interim_with_a_pending_row` (the push
  invocation is green on an in-flight interim bundle) and
  `closing_wire_demands_final` (the closing invocation refuses it).

## The parity line: what your host lacks vs what the lanes demand (P14-P0-2)

Run the gate on a laptop and you are not running the gate the runner runs.
Not an approximation: five distinct times this program has shipped a
local-green/hosted-red, and the fifth — actionlint runs its shellcheck pass
only when shellcheck is installed on the host — could not surface locally by
construction. `tools/ci_parity_check.py` (run early by `run_checks.sh`, wired
in `tools/checks/p14_gates.sh`) makes the difference a printed fact:

```
$ python3 tools/ci_parity_check.py
== ci-parity: local capability vs hosted lanes (P14-P0-2) ==
  optional tools (helper-tools.yaml + workflow installs + runner ledger):
    actionlint         present
    shellcheck         ABSENT (CI has this; the lane will be stricter there)
    ...
ci-parity: PARTIAL (N lane(s) will be stricter on CI: …) — exit 0 by design
```

The laws behind it:

* **Never a gate red.** PASS and PARTIAL both exit 0: a laptop legitimately
  lacks CI's tools, and a red gate would train people to install everything
  or ignore the lane. The enforcement is that the gate's **final tally echoes
  the verdict line** (`kr_finish` in `tools/checks/gate_runner.sh`) and
  `evidence/P<n>/report.md` §⑨ must quote it — a phase may not report "gate
  green" while the parity line says five lanes were weaker locally. A run
  that prints no `ci-parity:` verdict line IS a gate red (a run without a
  verdict is not a verdict).
* **Composite gaps are named as composites.** actionlint present but
  shellcheck absent prints its own row — "the shellcheck pass will not run
  here" — because the two individually-present rows would otherwise hide the
  one gap that mattered. Same for faketime (the ambient date probe is
  SKIP-visible locally, demanded on CI).
* **Entry-point modes and the sibling pin are reused, not re-implemented**
  (`tools/entrypoint_mode_check.py`, `tools/xr_sibling.py`); dev-dep
  installability runs the closure check's offline fixture path plus a live
  `pip install --require-hashes --dry-run`.
* **Network rows are re-proved at every run, never inherited.** One GET per
  allowlisted host through the `build/upstream/fetch.py` chokepoint (the only
  network call in the tree), under one deadline, with the api.github.com
  quota printed alongside — because the P13 incident was a 403 from a spent
  unauthenticated quota (`/rate_limit core 60/60`) being read as "the
  endpoint is private", and `chromium.googlesource.com` was a real 503 that
  was 200 hours later. A blocked row is a fact about *this run*, not a note
  for the next one. `ci_triage.py` classifies RATE-LIMITED and ADMIN-ONLY
  distinctly for the same reason (`classify_refusal`, C-0.7).
* **The tool proves itself.** `--self-test` (also a gate lane,
  `p14_parity_selftest`) must pass: it proves the verdict is a function of
  the host — the all-present case prints PASS, the gap case prints PARTIAL
  naming the gap — because a detector that always prints one verdict detects
  nothing. Registered negative: `tools/negatives/p14_p02.sh`.
