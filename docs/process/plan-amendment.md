# Master Plan amendment process

Status: in force since P1 (commit that lands `docs/master-plan.sha256`).
This document is S0 governance (dual senior review required).

## 1. The rule

`docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` is **pinned by SHA-256** in
`docs/master-plan.sha256` and verified by `tools/plan_pin_check.py` on every
CI run. The pinned file is **immutable in place**: no edit, re-wrap,
reformat, or "drive-by fix" — not even to fix a typo, not even by a
governance owner.

The plan is the single source of truth for this project (its own §0.4
ruling carries the same demand of us that it makes of specs: *deviation is a
stop-condition, not a default*).

## 2. What an amendment is

An amendment is a **new versioned file**, never an in-place edit:

1. **Record the deviation first.** File the deviation in
   `docs/state/research-log-P1.md` (or the successor log for the phase in
   which the need arose) with: the exact plan passage, why it is wrong or
   stale, the new external evidence, and the proposed replacement text.
2. **Decide it through the register.** A Decision Register entry
   (`docs/register/decisions.yaml`) captures the amendment decision —
   rationale, reopen condition, phase anchor — with the status flow
   ADR-0002 defines. Register-touching commits carry the
   `Register-Change: ADR-<nnnn>` trailer (ADR-0002 §2), enforced by
   `tools/dr_parse.py --check-trailers`.
3. **Write the new version.** Copy the pinned file to
   `docs/plans/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN_v<N>.md` (N = previous
   version + 1; v1 is the pinned original). Change only what the decision
   authorizes. A header comment at the top of the vN file records the
   version, the governing DR id, and the amendment commit.
4. **Re-pin and re-derive, in one commit.** In a single governance commit
   (dual senior review, S0 path):
   - update `docs/master-plan.sha256` to the new file's digest,
   - point `docs/XR_BROWSER_MASTER_IMPLEMENTATION_PLAN.md` to the new
     version (it remains a copy; the canonical vN file lives in
     `docs/plans/`),
   - regenerate derived artifacts: feature registry
     (`tools/gen_registry.py`), any ADR or register references to changed
     passages.
5. **Announce it.** The commit message states the DR id and the passages
   changed, so a future reader can diff vN−1 → vN and see exactly what
   moved.

## 3. What is NOT an amendment

- Fixing the *registry* to match the plan (the registry is derived; see
  `docs/registry/README` header inside `features.yaml`).
- Recording a finding that the plan is wrong — that is a *draft issue*
  (`docs/adr/draft-issue-<n>.md`) feeding §2 step 1, not a change.
- Local tooling or docs that merely *reference* the plan.

## 4. Enforcement

- CI: `tools/plan_pin_check.py` (digest equality, fail-closed).
- CI: `tools/registry_lint.py` (registry re-derived from the plan; any
  drift between plan and registry fails the build — so an in-place plan
  edit cannot pass unnoticed).
- The old version is never deleted: `docs/plans/` retains every vN.

## 5. P1 stance

No amendments are anticipated in P1. If any §2/§14 conflict between the
plan and primary-source evidence is found during P1, the correct action is
a **draft issue + register entry**, not a plan edit (e.g. the
keepass-rs 0.13.6 → 0.13.25 version drift was recorded in
`docs/dependencies/keepass-rs.yaml`, not in the plan).
