# Cross-repo pin process — xr-core → xr-browser (DEPS `xr_core_rev`)

**Status:** codified 2026-09-07 (P4-T0.2, debt D-B). **Owner:** A lead
(Platform/Chromium). **Enforced by:** `./scripts/build sync check-pin-alive`
(blocking in `governance.yml`).

Two repos, one product. `xr-browser` (meta) pins `xr-core` (product) by commit
SHA in `DEPS`:

```yaml
xr_core_rev: "c34cd6651ec5b4c4db0dbefa13357b1376057c25"
```

Everything the build, CI and the farm see is resolved **through that pin**,
never through `main`. A pin that does not exist on origin, or that origin has
moved away from, breaks every fresh clone at once — so the process below is
not optional.

---

## The rule

> **An xr-core commit and the meta-repo DEPS bump that consumes it land the
> same day, and the DEPS rev must be a reachable ancestor of origin
> `xr-core` `main` at the moment it lands.**

## Push modes (ruling, recorded P5→P6)

> **main-push remains sanctioned until HG-3/HG-10 (branch protection + PR
> flow) activate; from then, pair-bumps land via merged PR only.**

This records the P5 deviation (token-authorized direct main-push, noted in
`evidence/P5/human-gates.md`) as policy, not drift: until branch protection
exists on `xr-core` `main`, a same-day pair-bump push to `main` is the
sanctioned landing mode. The no-force-push rule above applies in ALL modes.

## Procedure (change a patch / add `//xr` code)

1. **Branch + commit in `xr-core`.** DCO sign-off
   (`Signed-off-by:`), one logical change per commit, no history rewriting.
2. **Push to origin `xr-core` `main`** — no force-push, ever. Let CI settle
   green before the bump if CI exists for that change.
3. **Record the SHA** (40 hex chars) of the pushed commit.
4. **In `xr-browser`, edit exactly one line** in `DEPS`:
   `xr_core_rev: "<new sha>"`. Nothing else in `DEPS` may change (Plan:
   "do not re-pin inside pins").
5. **Verify before committing:**
   ```bash
   ./scripts/build sync check-pin-alive     # ls-remote + fetch + merge-base
   ```
   Must print `object_present: true` and `ancestor_of_main: true`.
6. **Commit the DEPS bump in `xr-browser`** with a message naming both sides,
   e.g.
   ```
   build(deps): bump xr_core_rev to <short> — xr-core BUILD.gn + mount doc (XR-P4-T0.2)
   ```
7. **Push.** `governance.yml` re-runs `check-pin-alive` on the hosted runner;
   it must pass there too.

The two commits (xr-core change, meta DEPS bump) are a **paired change**. A
DEPS bump whose xr-core commit is not on origin is the exact failure mode this
process exists to prevent; the lint rejects it in CI.

## What `check-pin-alive` does

Unauthenticated, public remotes only — no token, no credential of any kind is
read or written:

1. `git ls-remote https://github.com/RRRTX-Labs/xr-core.git refs/heads/main`
   → the origin head SHA.
2. A scratch `git init` + `git fetch --no-tags origin main` (xr-core is small;
   a full fetch is cheap and makes ancestry decidable).
3. `git fetch --no-tags origin <pinned_rev>` → is the object even there?
4. `git merge-base --is-ancestor <pinned_rev> FETCH_HEAD` → is it on `main`?

Exit codes: `0` pass · `1` fail with the reason (unfetchable, or fetchable but
not an ancestor — i.e. diverged/rewritten) · `2` usage. **Fail-closed:** a
network error is a failure, never a skip and never an assumption that the old
SHA is still good.

## Failure modes and what they mean

| Symptom | Meaning | Action |
|---|---|---|
| `is not fetchable from <url>` | commit never pushed, or force-pushed away | push it, or re-point at a commit that exists |
| `is fetchable but is NOT an ancestor of origin main` | history rewritten, or the commit lives only on a branch | re-pin to a commit on `main` |
| `ls-remote ... failed` | network/DNS/allowlist problem on the runner | infra issue — **do not** paper over it by removing the check |

## Never

- Never point `xr_core_rev` at a branch name or a short SHA.
- Never force-push `xr-core` `main` after a DEPS bump has landed against it
  (the bump silently becomes a pin to a commit that only your clone has).
- Never edit `xr-core` inside `chromium/src/xr` and call it done.
- Never weaken `check-pin-alive` to make a red run green (P3's minisign lesson
  is the case study: make the dependency optional with a visible SKIP, never
  delete the gate).

---

## The verdict rule (P13-C-P0.2)

**A verdict computed from a sibling checkout is meaningless unless the sibling
is at the pin. The gate proves it or says BLOCKED-LAYOUT.**

Measured at `e503f9e`, `tools/coverage_check.py` resolved `../xr-core` by layout
guess (`Path(__file__).resolve().parents[1].parent / "xr-core"`) and imported
`commands` from it. Three outcomes, none of them a verdict:

| sibling state | what happened | why it is worse than a failure |
| --- | --- | --- |
| absent | `ModuleNotFoundError: No module named 'commands'` | reads as a broken environment, so an agent re-runs it and moves on |
| older commit | **vacuous PASS** | this is the one that shipped: P13-T1's predecessor had a local `../xr-core` that predated the panel files, so the landed-surface scan found nothing to bite and every local run was green while the hosted run was red |
| dirty tree | HEAD matched the pin, files did not | the comparison is true about a tree nobody read |

### The three typed refusals (all exit 2 — "usage", because a gate that cannot
see its inputs has not rendered a verdict)

```
BLOCKED-LAYOUT: no xr-core at <path> — this gate computes its verdict from the
                sibling checkout, so an absent sibling is BLOCKED, not a pass
STALE-SIBLING:  have <sha>, want <pin> — the sibling is not at DEPS.xr_core_rev
DIRTY-SIBLING:  uncommitted changes at <path> — HEAD agrees with the pin but the
                tree does not, so the files read are not the pinned files
```

`STALE-SIBLING` always prints **both** shas: a refusal that does not name the
expected value cannot be acted on, and "wrong sibling" without the target is a
debugging session rather than a fix.

### Where the law lives

* `tools/xr_sibling.py` — the ONE resolver. `check()` returns a verified
  `Sibling` or raises `SiblingError`; `resolve_or_exit()` is the command-line
  form. No tool may compute `../xr-core` for itself.
* `build/qa/_common.py::xr_core_root()` — the pre-existing utility that ~20
  build kits already call. It now **delegates** to the resolver instead of
  checking existence only, so those callers inherit the pin law without a second
  copy of the path logic.
* `tools/sibling_pin_check.py` — the gate. It PROVES the pin and AUDITS the
  register: every file in the tree that resolves a sibling path is classified
  (`routed` / `gate-ordered` / `arg-only` / `probe` / `test` / `self`), and an
  **unclassified** reader is a FAILURE, not a warning — the class grows back the
  moment a new tool guesses, and it must not be able to do so silently. A
  `routed` entry is checked textually against its file, so the register can
  never claim a fix that is not there; `gate-ordered` entries are checked
  against the ORDER in `tools/run_checks.sh`, so "runs after the pin lane" is
  verified rather than asserted.
* `tools/run_checks.sh` — `p13_sibling_pin` runs BEFORE every lane that consumes
  the sibling.
* `.github/workflows/governance.yml` — the same lane runs as its own step
  immediately AFTER `Checkout xr-core at the DEPS pin` (the ordering precedent
  P12-CLOSE's `8db682f` established), so the diagnosis is a one-line failure at
  the top of the run rather than a forty-minute red.

### A nonstandard layout is a flag, not a skip

`--xr-core <path>` exists on every routed tool and on the gate. An override is
**not** an exemption: every check still applies to the path it names, including
the pin comparison and the clean-tree law. There is deliberately no flag that
turns the law off — `--no-verify` style escape hatches are how a gate becomes
decorative.

### Negatives (`tools/negatives/p13_c02.sh`, N=4)

1. a sibling one commit behind ⇒ `STALE-SIBLING` with **both** shas in the
   message;
2. a sibling absent ⇒ `BLOCKED-LAYOUT`, exit **2** — not exit 0 (the vacuous
   pass) and not a traceback (the ImportError that reads as a broken
   environment);
3. a routed **verdict** tool run with no sibling ⇒ exit 2, the typed line, and
   **no verdict printed** — this is the case that pins the helper's *use*, so a
   tool cannot import it and forget to call it;
4. an unclassified sibling reader ⇒ the audit reddens and names the file.

### Debt this leaves, named

Fourteen tools are registered `gate-ordered`: their sibling reads happen after
the pin lane in `tools/run_checks.sh`, which the audit verifies. Routing them
individually through `resolve_or_exit` (so they can also be run standalone
against a proven sibling) is proposed for **P14**, where the panel's identity
queries add two more sibling readers and the register will need re-review
anyway. Until then the register makes them visible, and a new one cannot land
unclassified.
