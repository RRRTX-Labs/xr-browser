# Window/tab identity binding (P14-T3)

Status: the binding MODEL is shipped + tested
(`xr-core/identity/core/binding.{h,cc}`, `tests/test_binding.cc`); the UI
half (dialogs, menus, the visual pill) consumes it and can add nothing the
laws here forbid.

## The laws

* **Default identity per window.** A tab is born at its window's default;
  an explicit opener domain is the right-click "Open tab in identity…"
  path. A window with no default refuses to open tabs (fail-closed).
* **Move-across-identity is destructive: confirm + reload.** A move onto a
  tab that has ALREADY navigated is refused with the ceremony named in the
  error (`kNotPermitted (after_nav: move requires confirm + reload)`) —
  the P4 timing finding: a non-destructive attach does not exist. The API
  never reloads on its own; the confirm is the caller's contract (and the
  confirm names what is lost).
* **Groups cannot span identities — enforced in the move logic, not the
  UI.** A move that would split a group is refused and names the blocking
  peer (`peer 202 is in another identity`). The whole group moves as one
  confirmed action (`group_peers` carries each peer's domain after the
  move).
* **Site→identity is a suggestion, never a switch.** `never auto-switch`
  is STRUCTURAL: the single mutation point refuses the suggestion cause
  outright (`test_binding.cc` plants the auto-switch and proves the
  refusal; the fuzz oracle checks the audit trail continuously). A
  suggestion is recorded and surfaced (`suggest` → `surfaced: true`), and
  no code path can apply one.
* **Every change is audited** with its cause: window-default,
  user-confirmed-move, restore. (Session restore is T8; the model's
  `RestoreTab` records the cause now.)

## Invocation

`identity_host bind-open '{"window":"w1","tab_id":101}'` ·
`bind-move '{"from":"xr:…","to":"xr:…","tab_id":101,"after_nav":false}'` ·
`suggest '{"site":"mail.example","domain":"xr:…"}'` ·
`autoswitch-probe '{…}'` (MUST be kRejected) · `audit`.

## NOT-RUN (methods, not surrogates)

The move-confirm usability study (6 non-engineer participants) and the SR
announcement audit are people, not CI — `docs/qa/browser-harness.md`
records the method; HG list carries the gate.
