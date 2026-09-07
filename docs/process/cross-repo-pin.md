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
