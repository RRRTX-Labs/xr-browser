# Identity templates (P14-T2)

Status: engine shipped + machine-checked
(`xr-core/identity/core/templates.{h,cc}`, `tests/test_templates.cc`).

## The seven

Personal · Work · Research · Banking · Shopping · Disposable · Tor — each
a named, reviewable set of overlay rows (`prefs:` / `policy:` / `visual:`)
applied at provisioning. `identity_host templates` lists them; the palettes
are data in `templates.cc` (Tor violet `#78288c`, Disposable amber
`#f9ab00`, …).

## The ceremony inventory (Spec-A §3.9, machine-checked)

Every creation ceremony lists EVERY default applied. The inventory is
GENERATED from the same rows `ApplyTemplate` writes — a single source of
truth, so the list cannot drift from the application:

* a default that applies without being listed ⇒ the completeness checker
  reddens (`test_templates.cc` §3, both directions);
* adding a default to a template without its ceremony line is therefore
  unshippable — the test is the law, not a review convention.

`identity_host ceremony '{"template_id":"banking"}'` returns the lines.

## Inert-with-reason (the P12-T6 honesty law)

A template that is inert must SAY it is inert and why:

* **Tor** is a template NOW; route binding lands P31. The shape exists
  (violet border, `net.route=tor`, `net.auto_update=off`), `route_bound` is
  false, and the ceremony text says "NOT BOUND YET — nothing claims Tor
  routing works today". No endpoint is added (the egress/fetch allowlists
  are untouched).
* **Disposable** states the zero-bytes posture in its ceremony (in-memory
  partition; `vault.access=none` from birth; the FS-diff assertion is T6).

## Banking is restrictive at birth

strict trust, `session.persistent_cookies=off` (no durable auth cookies),
`net.webrtc=disable_non_proxied_udp`, prefetch off — overlay rows a user
cannot forget to set.
