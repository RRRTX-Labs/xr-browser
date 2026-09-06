# Pinned GitHub Actions (full SHA, no tags)

Supply-chain discipline (Plan §9.11/§13): every action is pinned by full SHA;
a floating `@vN` tag is never used. Bumping a pin is a PR whose commit message
records the tag→SHA mapping. Verified 2026-09-07 via the GitHub REST API
(`GET /repos/<owner>/<repo>/git/ref/tags/<tag>`).

| Action | Tag | SHA (pin) | Used in |
|---|---|---|---|
| actions/checkout | v4.4.0 | `11d5960a326750d5838078e36cf38b85af677262` | governance.yml, ci/*.yml |
| actions/setup-python | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` | governance.yml |
| actions/upload-artifact | v4 | `ea165f8d65b6e75b540449e92b4886f43607fa02` | ci/nightly-rebase-build.yml |

Notes:
- `upload-artifact@v4` is a moving major tag; the SHA above is the v4 tip at
  pin time (2026-09-07). It is pinned by SHA regardless of the tag moving.
- P1 carried checkout + setup-python; P2 adds upload-artifact (the nightly
  SBOM/budget artifacts) — this file is the single registry of those pins.
