# Contract-amendment procedure (T10, L14)

Once a contract is stamped in `FROZEN.yaml`, changing its IDL/schema/doc
requires an **approved RFC**. This mirrors the Register-Change trailer machinery
(`tools/dr_parse.py`) and is enforced by `tools/amend_guard.py`.

## Procedure

1. Draft `docs/rfcs/RFC-<n>.md` from `docs/rfcs/0000-template.md`
   (status starts `DRAFT`, then `PROPOSED`).
2. A commit that touches `xr-core/mojom/**` or a frozen contract doc MUST carry
   the trailer `Contract-Amendment: RFC-<n>` AND `docs/rfcs/RFC-<n>.md` must
   exist with `status: APPROVED`.
3. **Pre-stamp** (before a file appears in `FROZEN.yaml`): `amend_guard` is
   **warn-only** (drafting is free during the freeze itself).
4. **Post-stamp:** a touching commit without the trailer, or with an RFC that is
   not APPROVED, **fails CI**.

Approval of an RFC is a human act (recorded by a human setting `status:
APPROVED`); an agent never self-approves. Additions to the §1.11 list are RFCs
per T10 — never silence.
