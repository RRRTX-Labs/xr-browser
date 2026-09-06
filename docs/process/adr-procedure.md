# ADR procedure

Applies to every ADR in `docs/adr/` and to every Decision Register change in
`docs/register/decisions.yaml`. Codifies Plan L14 ("Contracts are documented
or they don't exist"), Plan §14 L24 (agents follow humans' contracts), and
the P5-T10 contract-amendment flow (which reuses this procedure for
`//xr/mojom` contracts from P5 onward).

## 1. When an ADR is required

An ADR is required when any of the following is true:

- a Decision Register row (DR-xx) is proposed to change status;
- an architecture seam, interface, license, or legal posture changes;
- a Plan section is contradicted by new evidence (do **not** edit the Plan
  copy — file the ADR; see `plan-amendment.md`);
- an S0 path (§7.2) gains a new mechanism or loses one;
- a dependency is adopted, rejected, or replaced (L9 evaluation pack first,
  then the ADR cites it);
- a budget or invariant number changes (e.g. patch budget, perf budgets).

Not every task needs an ADR — routine phase work inside an existing
decision needs none.

## 2. Authoring rules (human authority, L24)

- **Coding agents never author decisions.** They may produce *drafts*:
  proposed text, evidence gathering, impact analysis. The draft must say
  so in the decider line.
- **Named humans decide.** The `Deciders (humans):` line lists the people
  (or role + name) who approved. ADRs without a named human decider cannot
  be marked ACCEPTED — CI cannot know a human signed, so the review
  workflow (CODEOWNERS dual review on `docs/adr/` and `docs/register/`)
  enforces this.
- ADRs are append-only history: supersede, don't rewrite. A SUPERSEDED
  ADR keeps its original text and gains a `SUPERSEDED-BY-ADR-NNNN` status.

## 3. Numbering

- 4-digit zero-padded, sequential, never reused (ADR-0002).
- `docs/adr/RESERVED.md` lists held numbers (currently: **0042 → P4
  identity-seam ADR**).
- Filenames: `NNNN-<kebab-slug>.md`; the slug is stable once accepted.

## 4. Lifecycle

```
PROPOSED → (human review; S0 topics: dual senior review incl. Security, L13)
        → ACCEPTED  | REJECTED
ACCEPTED → (new evidence) → SUPERSEDED-BY-ADR-NNNN
```

- **PROPOSED:** context + decision + consequences written; evidence linked.
- **ACCEPTED:** decider line complete; any linked register change lands in
  the **same PR** with the `Register-Change: ADR-<nnnn>` trailer.
- **REJECTED:** keep the file — a rejection with reasons is evidence.
- **SUPERSEDED:** only via a new ADR that names the old one; the old file's
  status line is updated in the same PR.

## 5. Decision Register changes (DR-xx)

1. New **written** evidence (external source, measured spike, or legal
   verdict) — never preference.
2. New ADR: title names the DR (`ADR-00NN: DR-xx — <change>`).
3. Register edit in the same PR: status change + `superseded_by` note
   appended; the original `rationale` text is **never rewritten**.
4. Commit trailer: `Register-Change: ADR-<nnnn>` (enforced by
   `tools/dr_parse.py --check-trailers` in CI).
5. If the change touches a §2 S0/S1 feature row's model entry, the threat
   model (`docs/threat-model.md`) is updated in the same PR — shipping a
   feature that changes the model without updating the model is a blocked
   merge (Plan §9.1 rule, machine-checked by `tools/check_threat_model.py`).

## 6. Contract amendments (from P5)

P5-T10's contract-amendment RFC procedure is **this procedure applied to
`//xr/mojom`**: an interface change is a contract change → ADR required →
frozen interfaces cannot gain side channels (L4) → fakes and fixtures are
updated in the same PR (L14). Until P5, no contracts exist, so this section
is forward-declared, not operative.
