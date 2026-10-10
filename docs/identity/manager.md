# The identity manager: `xr://identities` (P14-T7)

Status: a DEV page. Its model, gate, view core and laws are shipped and run
here (P14-CLOSE C-3). The rendered page in a WebUI host is NOT-RUN: there
is no browser build (method at the bottom).

## Dev only, by enforcement

The page uses the same enforcement as `xr://shield`. It is not a promise in
a comment:

* the roster command `identities.page` is tier 2 and rides
  `build.channel-dev`. Off dev it is listed but disabled, with the reason;
* `identity_host` takes a real `--build-channel dev|nightly-test|release`
  option that **defaults to release**. `manager-page` and `reset-all`
  answer every non-dev channel with
  `{error: "kRejected", reason: "build-channel-not-dev:<channel>"}` and no
  page bytes. An unknown channel is a usage error (exit 2);
* `DevChannel()` in `xr-core/identity/core/manager_page.cc` fails closed:
  only the exact string `dev` passes;
* the view's `resetAllAllowed()` demands the dev channel AND the typed
  phrase `reset-all`.

`tools/shield_state_check.py` (extended through
`tools/identity_page_states.py`) checks all of this structurally, and the
negatives in `tools/negatives/p14c_c3.sh` plant each bypass.

## What the page shows

`BuildManagerPage` (`xr-core/identity/core/manager_page.h`) is the model:

* **states**: `normal`, `empty`, `purge-unverified`, `dev-refused`. The
  view renders every state, with an honest-unknown default;
* **per identity**: tab count (the binding's latest row per tab), storage
  bytes (the purge-verify walk: surface plus out-of-place residual), and
  permission count (from the permission overlay; absent is `null`, never a
  guessed 0);
* **edits**: rename, recolor and archive change display metadata only,
  never the opaque domain. A rename the domain would appear to embed is
  refused (the opacity law), and refusals never echo input. Display names
  are capped at 64;
* **purge and reset-all**: any unverified purge raises the page to
  `purge-unverified`, and the residual kinds are named. `reset-all` purges
  and verifies every identity and returns
  `{all_verified, destroyed, results[]}`. One planted residual makes
  `all_verified` false.

Archive is hibernate. A distinct archived state belongs to the manager
mojom, which is review-complete and not ratified (HG-26). Creating an
identity stays the host's provisioning path (`docs/identity/provisioning.md`).
The seam the whole identity system rests on is recorded in
`docs/state/research-log-P14.md` §"seam decision".

## Where it is proved

* `xr-core/identity/tests/test_manager_page.cc` (every state, every edit
  refusal, the dev gate), mapped into the identity mutation lane.
* `build/webui/identities-page-tests.sh`: the TS core runs under node:test
  against the compiled host's LIVE replies for every page state. Its
  `--plant-drift` must redden.
* `tools/tests/test_p14c_identities_page.py`: every channel, the usage
  error, stats, edits, purge-unverified and reset-all.

Transcript: `evidence/P14/logs/c3-identities-page.txt`.

## NOT-RUN (method, not a surrogate)

Load `xr://identities` in a dev build, walk every page state and the
reset-all confirmation, and confirm a release build refuses the URL:
`docs/qa/browser-harness.md#identities-page-rendered`.
