"""build/spike/ — the P4 identity-seam spike toolkit.

Stdlib-first (zero new dependencies), same house style as the rest of
build/: typed, --json, exit 0 pass / 1 fail / 2 usage, <400 LOC per file.

Modules
  genpatch     real apply/verify/revert round-trip of the 0042 seam-hook
               candidate patch against actual pinned-rev Chromium files
               (fetched through build/upstream/fetch.py — the only network
               choke point). This is P4's "proven in code, at source" anchor.
  seam_spec    the transform description genpatch applies (targets, anchors,
               payload files) + the never-list path policy.
  fsdiff       real filesystem diff (hash every path pre/post) for the
               ephemeral zero-residual claim.
  cdp          minimal stdlib WebSocket/CDP client (RFC 6455) used by the
               probe driver to read process-internals; no vendored library.
  probe_driver runs the probe lanes (--offline today, --farm on hardware).
  citation_audit  re-fetches every file:line citation in the spike docs at the
               pin and verifies the quoted text is actually there.
  census_lint  enforces the papercut census schema (Plan's 12 named surfaces).
"""
