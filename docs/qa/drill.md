# Drill kit — update-drill + crash/recovery (P9-T10/T11)

Two drills, one shape: **matrices as data** (`build/qa/drill/*.yaml`) +
**a farm runner** (`build/qa/drill/drill_run.sh`) + **a data gate**
(`tools/drill_check.py`). The matrices are owned and validated here; the
execution needs a real browser process tree and a per-OS VM farm, which do
not exist in the P9 sandbox — so the runner is SKIP-visible (exit 77),
never a fabricated pass.

## Kill matrix (§11.10, P9-T11)

`build/qa/drill/kill-matrix.yaml`: the 8 process types
(browser/renderer/network/vaultd/tord/wgd/inspect/gpu) × kill signal, under
the 50-workspace × 40-tab load profile, each with assertions that map
one-for-one to the §11.10 clauses:

- session-restore correctness
- ephemeral-zero-residue post-crash (FS-diff)
- fail-closed route behavior on helper death
- no identity bleed on restore
- crash-loop safe-mode
- beta crash-rate ≤1.2× prior stable (auto-halt wired)

## Update drill (§11.11, P9-T10)

`build/qa/drill/update-drill.yaml`: per-OS (linux/macos/windows) snapshot/
restore with a kill-mid-update interruption point per OS, asserting
resume-or-rollback (no bricked state) and rollback-to-prior-version with
data intact, plus the P10 extras (update-epoch revocation, the failed state
with a manual-download pointer).

## Gate laws (tools/drill_check.py)

1. **Empty-run** — zero rows is a failure.
2. **Complete** — all 8 process types and all 3 OS present.
3. **Asserted** — a row with no assertions is a failure (delete one and the
   gate goes red — the canary).
4. **Honest runner** — `drill_run.sh` must SKIP visibly (exit 77, "SKIP" in
   output) without the farm binary.

## Farm rows

| row | command | farm requirement |
|---|---|---|
| HG-33 kill matrix | `drill_run.sh kill-matrix` | browser process tree + VM snapshots |
| HG-34 update drill | `drill_run.sh update-drill` | per-OS VM farm (snapshot/restore) |

## In-sandbox command

```sh
python3 tools/drill_check.py --repo .   # PASS: matrices complete + honest
```

## P10 correction (T0-b): the execution deferral was over-claimed

P9 recorded execution as deferred because "a real browser process tree and a
per-OS VM farm do not exist in the P9 sandbox". True for the 8 Chromium
process types — **false for the four host binaries that ship in xr-core**
(`policy_host`, `commands_host`, `settings_host`, `themes_host`). P10-T0-b
closes exactly that gap:

* `drill_run.sh hosts-local` (backed by `tools/kill_matrix.py`) executes the
  matrix **for real in-sandbox** against every discovered `*_host` target:
  kills mid-write / mid-dispatch / mid-snapshot under SIGKILL and SIGTERM,
  calibrated against each host's measured runtime so kills land mid-flight.
* Asserted after every kill: no partial state (state files always parse,
  whole known generation), prior-state-preserved (the store still loads and
  answers), corrupt-load preserve (a truncated file is never silently
  rewritten), and disposable ⇒ zero bytes.
* The split is printed every run (cells executed / cells not-run with
  reasons); **0 executed ⇒ FAIL** (the build/qa/_common.py law).
* `policy_host`'s mid-write cells stay NOT-RUN with the honest reason (its
  binary has no write mode — `PolicyStore::Save` is library-level until the
  P11+ IPC adoption), and the 8 Chromium process rows stay farm-visible
  (HG-33) in the same split. Nothing was re-quieted; P9's closed DoD rows
  stand as recorded, corrected here.
