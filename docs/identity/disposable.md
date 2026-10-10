# Disposable identities (P14-T6)

Status: the model halves are shipped and run here (purge AND verify, the
FS-diff harness, the matrix cell, the session drop). The real-browser
FS-diff is NOT-RUN: there is no browser build to diff (method at the
bottom).

## What "disposable" promises, and what it does not

The published limitation is the contract (Plan §1.13, copied verbatim in
`docs/limitations.md`): "Disposable = browser-side forgetting, not forensic
erasure, not network anonymity." A disposable identity keeps its data in
memory (`in_memory: true`, so the partition has no on-disk path; measured
row S-19 in `docs/spike-identity/measured-shared-state.md`). Closing it
must leave zero bytes the browser wrote for it.

## The laws

* **Close = purge AND verify.** The host's destroy computes
  `zero_residual_verified` by walking the store after the purge; the
  purge's own return code is never trusted. Any residual bytes make the
  destroy FAIL and name the bytes (`docs/identity/lifecycle.md`). The
  planted cookie jar negative proves the walk bites.
* **No resurrection.** Waking a purged identity answers
  `kUnknownIdentity`; it never re-mints one silently
  (`xr-core/identity/tests/test_hibernate.cc` §4).
* **Never restored.** A session snapshot does not write disposable-bound
  tabs, and restore drops them and REPORTS the drop
  (`docs/identity/restore.md`). A crash cannot bring a disposable back.
* **No Fortress promotion.** Promoting would persist the volatile, so it
  is refused with the reason.
* **No vault.** The resolver fake gives the ephemeral identity
  `autofill_allowed: False, export_allowed: False` (the "no vault access"
  row). The row is consulted on the path: stubbing the consult (absent,
  or granting) makes the check fail (`tools/tests/test_p14c_security.py`,
  P14-CLOSE C-4).

## Where it is measured

* `build/spike/fsdiff.py`: sha256 + size per path, no ignore lists,
  symlinks recorded and not followed (tests: `build/spike/tests/test_spike.py`).
* Isolation matrix cell `disposable-zero-residue`: every identity pair in
  fake mode. The cell runs `fsdiff` around each cycle and must catch a
  planted leftover; neutering the diff turns the cell FAIL
  (`tools/tests/test_p14c_security.py`). It shows
  on the Isolation Card as `holds` with 5 of 5 pairs measured
  (`docs/limitations.md`, generated block).

Transcripts: `evidence/P14/logs/t5-t6-isolation-matrix.txt`,
`evidence/P14/logs/c4-security.txt`.

## NOT-RUN (method, not a surrogate)

Snapshot the real profile directory, run a disposable create / use /
destroy cycle, snapshot again and assert an empty diff, using
`build/spike/probe_driver.py` around `fsdiff.py` on the farm:
`docs/qa/browser-harness.md` (Disposable zero-bytes close, P14-T6).
