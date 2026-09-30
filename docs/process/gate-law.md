# Gate law (P13-C-P0.1c)

Short, named rules about what a GATE may and may not be. Each one exists
because this repository paid for it: a defect that shipped green. A rule here is
only added once the defect has been reproduced, its fix has a registered
negative, and the rule has been cited from the code that enforces it.

---

## 1. A verdict-bearing assertion compares derived values, never an embedded number

**The law.** If an assertion decides pass/fail from a quantity that drifts as
the repository grows, that quantity must be **computed at assertion time** from
the artifacts in front of it. A number typed into a test, a gate, or a comment
is not a check — it is a promise that every future phase will remember to edit
it, and the phase that forgets is always a later one, so it fires at the worst
possible moment: on an unrelated change, far from its cause.

**Reproduced at** `e503f9e`, `tools/tests/test_p8_t5_l10n.py:48`:

```python
assert "OK (127 messages" in r.stdout  # P11-T6: +36 shield; P12-T6: +14 cosmetic
```

The comment is the tell: three phases had edited that number, and P13 (the +5
`panel.tab.*` titles) had not. The **tool** was green — `grdp_check` reports
what the file holds (136) — and the **test** was red, so the gate was reporting
a fact about its own bookkeeping and calling it a fact about the tree. The
preceding turn's triage annotation read exactly that:
`governance: tools/tests/test_p7_commands_tools.py::test_coverage_check_real_passes
- AssertionError: assert 1 == 0` — the same class, one phase earlier.

**The fix is removal, not refresh.** Refreshing `127` to `136` reproduces the
defect with a fresher number. The number is gone: `tools/l10n_count_law.py`
compares the count the tool *reports* (parsed from its own captured stdout)
against an **independent** count of `<message>` elements in the same file, and
then against a grow-only ratchet (`docs/qa/l10n-ratchet.json`).

**Why the ratchet is a file and not a literal.** Decrease detection has to
freeze *something*. Freezing it in a data file means raising the floor is a
reviewed act that shows up in a diff, while adding a string needs no edit at
all — the opposite of the literal's economics. Shape precedent: P8's
`ratchet: "916 (grow-only)"` row in `docs/state/perf-budgets.json`.

**Registered negative.** `tools/negatives/p13_c01c.sh` feeds the law a **stale
transcript** — a `.grdp` that grew one message while the tool's captured stdout
still reports the old count — and requires it to redden, with the pair in
agreement required to pass. Without that case the law would be an assertion
about a quantity that happens to agree, which is exactly the vacuity this rule
removes.

**The grep, and every hit.** Per the phase brief:

```console
$ grep -rn 'assert ".*[0-9]\{2,\}' tools/tests/ | grep -iE "messages|cases|count"
tools/tests/test_p8_t5_l10n.py:48:    assert "OK (127 messages" in r.stdout ...
```

One hit, fixed here. `.sh` analogues (`tools/checks/*.sh`, the `N=`/`cases`
shapes): **none**. The remaining numeric assertions in `tools/tests/` are law
*constants* or fixture-local, and are not this defect:

| site | why it is not this defect |
| --- | --- |
| `test_p10_kill_matrix.py:64` (`loc < 400`) | the LOC ceiling is a constant of the law, not a quantity that drifts |
| `test_entrypoint_mode.py:96` (`== "100755"`) | a file mode: a fixed token, and the assertion is *about* that token |
| `test_p8_settings_themes.py:266` (`== 200`) | fixture-local: the test built those 200 queries in the same function |
| `test_blink_guard_lint.py:83` (`"0200"`) | a patch id read out of the fixture it just wrote |
| `test_plan_pin_check.py:45` (`== PIN`) | `PIN` is a module constant derived from the file, not a literal in the assertion |

**This is the third time this repository found this defect**, which is why it is
now named. The two earlier finds, both fixed in their own phase:

* P10's perf-budgets hand-edit refusal — a budget value edited in the committed
  JSON must redden the generator's `--check` (`build/qa/perf/gen_perf_budgets.py`);
* P13-P0-C's negatives harness — `f969499` made the case count **derived** at
  source-time from registration, because a hard-coded `N` "is a lie waiting to
  happen", and separately stopped verdicts riding a pipeline exit code.

**Where it is enforced.** `tools/checks/p13_gates.sh:p13_l10n_count_law`, called
from `tools/run_checks.sh`, plus `tools/tests/test_p8_t5_l10n.py` (three tests:
agreement, ratchet, and the stale-transcript negative asserted from pytest too)
and `tools/negatives/p13_c01c.sh`.

---

## 2. A gate may not render a verdict it cannot source

**The law.** A verdict computed from an input the gate has not proven — a
sibling checkout at the wrong commit, an absent directory, an unreadable
artifact — is not a weak verdict; it is a **false** one, and it is worse than a
failure because it is reported as a pass.

**Reproduced at** `e503f9e`, in two directions:

* `tools/coverage_check.py` with **no** `../xr-core`:
  `ModuleNotFoundError: No module named 'commands'` — an error that reads as a
  broken environment, so an agent re-runs it and moves on;
* the same tool with a **stale** `../xr-core`: a vacuous PASS, which is exactly
  how the `panel/focus-trap` red reached the pin while every local run was green.

**The fix.** `tools/xr_sibling.py` resolves the sibling once for the whole tree
and proves it is at `DEPS.xr_core_rev` and clean; failures are typed
(`BLOCKED-LAYOUT`, `STALE-SIBLING`, `DIRTY-SIBLING`) and exit 2. Rule of record
in `docs/process/cross-repo-pin.md`. Enforced by `tools/sibling_pin_check.py`
over every sibling-consuming tool (P13-C-P0.2).

---

## 3. A law binds when it is CLAIMED, not when a directory name implies it

**The law.** An obligation that triggers on *position* (the newest entry in a
list, the file with the largest number) makes its own compliance impossible for
whoever happens to occupy that position. Closure is a claim: a commit that
closes a phase says so with a trailer, and only then does the closing law bind.

**Reproduced at** `e503f9e`: `--require-phase-final` triggered on *being the
newest phase in `docs/state/phase-base.json`*, so no in-flight commit could ever
be green — the law kept `governance` red for the whole of every future phase
while reporting an unsatisfiable demand.

**The fix.** `Phase-Close: P<n>` trailers (validated the way
`tools/dr_parse.py --check-trailers` validates `Register-Change:`); without the
trailer the lane prints
`finality: P13 interim (phase open; no closure claimed) — not a verdict` and
passes. Enforced by `tools/evidence_finality.py` (P13-C-P0.3).

---

## 4. A cited path that does not exist is not a method

**The law.** `NOT-RUN (method: <path>)` is only honest if `<path>` exists. A
dangling citation launders an unmeasurable claim into a documented one, and no
reader can tell a deliberate deferral from a fabrication without opening the
file.

**Reproduced at** `e503f9e`: `evidence/P13/human-gates.md` cites
`docs/panel/breakage-report.md` twice as the HG-33 drill method, and
`ls docs/panel` → no such directory.

**The fix.** `tools/reference_check.py` extracts every `docs/…`, `evidence/…`,
`build/…` path cited in any bundle, `human-gates.md` and report, and FAILs on a
missing one; the dangling-reference negative is registered
(`tools/negatives/p13_c05ref.sh`). P13-C-P0.5.
