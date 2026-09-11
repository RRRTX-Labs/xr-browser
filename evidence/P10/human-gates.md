# evidence/P10/human-gates.md — the human gates this phase records

Every row is an act this sandbox cannot and must not fake. Each names the
exact operator steps and the credential it needs.

| id | gate | why human | operator steps (exact) | status |
|---|---|---|---|---|
| HG-36 | Key ceremony + HSM custody (root `xr-root-1`, per-platform keys) | two-person, air-gapped, hardware-born keys | `release/keys/ceremony.md` steps 0–6 (ykman PIV keygen, fingerprint, backup, test-artifact signing, evidence MANIFEST) | NOT-RUN (no HSM; `tools/secret_scan.py --all` proves zero key material — ADR-0004) |
| HG-37 | Code-signing certificates + notarization + SmartScreen | paid, legal-reviewed, vendor accounts | `docs/release/signing-runbook.md` (mac: codesign/notarytool/staple; win: signtool EV+HSM; Linux repo keys via HG-36) | NOT-RUN (no Apple Developer account, no EV cert; the gate refuses release channels fail-closed) |
| HG-38 | Update-server hosting + egress approval | org decision; new network egress | `docs/release/server.md` + `release/egress-allowlist.json` review; deploy the std-only Rust server behind the approved host | NOT-RUN (nothing hosted; `attest.py --publish` SKIPs visibly) |
| HG-31/35 | Three-OS rollback rehearsal (farm) | physical Apple/Windows hosts + real notarized builds | `docs/release/rollback-drill.md` (run the 10-cell drill per OS against staging, force the epoch flip from the ceremony HSM) | NOT-RUN (local drill runs 10/10 cells here; the 3-OS sweep is farm) |
| HG-28 | 24 h full-mutation matrices (farm-time) | wall-clock farm budget | `tools/mutation_test.py --targets <all> --sample 0` per core at the release pin | PARTIAL (local full matrices: policy 777, settings 485, themes 386, commands 414, update 415 — all green; the 24 h farm cadence remains) |
| HG-20 | PAT revocation re-flag | user action | revoke the over-scoped PAT exposed in chat (three-plus occurrences), rotate if ever used | OPEN (carried from P9; still user-owned) |
| HG-26 | Ratify-or-amend the five living-contract consumers before P11 | sign-off act | P6 policy, P7 command-descriptor, P8 settings/theme, P9 evidence format, P10 update-manifest + the six new P10 contracts (`registry-post-freeze.md` P10 section) | OPEN (one-batch ratification recommended before P11) |
