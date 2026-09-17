# The generic hide set (P12-T3)

`xr-lists/generic-hide-set.v1.json` — 33 selectors, always on, not
exception-able at the Shield policy level. `tools/cosmetic_generic_set_check.py`
enforces the properties below; four plants verified red (a `position`
declaration, a `page_modifying` mismatch, an unparsable selector, a stale
budget).

## Why it is always on

The generic set is the one cosmetic rule set that does not come from a
subscribed list. That is what makes it possible to ship cosmetic filtering with
both flags off by default and still have the surface mean something when it is
turned on: a user with zero lists installed gets the well-known junk hidden, and
a user who unsubscribes from every list does not get a page whose layout depends
on a list they no longer have.

`no_upstream_list_required: true` is asserted in the file and checked, because a
generic set that needed a subscribed list would not be generic — it would be a
default list with a different name, and the always-on property would inherit
that list's failure modes.

## Why it is not exception-able

This is a **reading of the plan, recorded rather than silently chosen**, because
the plan says "generic hide set always-on" without saying what happens when a
user lowers shields on one site.

The reading: cosmetic rules *from a list* remain exception-able per site; this
set does not. The reason is that a shields-down must not leave the page
half-styled. If the generic set were per-site exception-able, a user who lowered
shields on one site would get a page where the site's own rules were off but the
generic ones were still applying — a rendering that is worse than either
consistent state, because the user cannot tell which rules are in effect and
cannot make the page consistent by any available control.

`exception_able_at_shield_policy_level: false` and an `exception_note`
explaining this are both required fields; the checker fails without them. If
this reading is wrong, the correction belongs in the ADR and in that note, not
in a code path nobody documented.

Note what the flag still governs: with `xr_shield_cosmetic_v1=false` the generic
set does **not** apply either, and `page-states` reports
`generic_set_applies=false`. "Always on" means always on *when the feature is
on*. An off state that still applied a rule set would not be an off state, and
the off state is asserted identical to today's product.

## What is in it, and what is not

Every entry matches an element by its **role in the page**, never by domain and
never by a list author's opinion about a site. Three shapes:

- **the page's own declaration** — `div#ad-placeholder`, `div#ad-slot-empty`,
  `div[data-sponsored=true]`. The page has already labelled the element; hiding
  it cannot remove content the author intended the reader to see.
- **the network's own published state** —
  `ins.adsbygoogle[data-ad-status=unfilled]`. Reading the network's signal is
  more reliable than guessing from a class name, and the selector only matches
  when the network says the slot is empty.
- **element-level junk that covers content** — a soft wall's overlay, a scroll
  lock, a cookie wall, an app-install prompt. Not ads, which is why they are in
  the *generic* set rather than a list.

Four entries are `page_modifying: true` (three `remove` actions and one style
rule that lifts a scroll lock). They are labelled so the Observatory does not
report an injection or a removal as a blocked request — an injected or removed
element is not a blocked request, and conflating them makes the event schema
lie.

Deliberately absent:

- **`position` and `z-index` declarations.** A rule that can restack a page can
  hide the *user's* content instead of the ad's, which is a UI-spoofing channel.
  The checker refuses both by name.
- **Any selector with a domain in it.** A generic set that matched by domain is
  a list.
- **`remove` as a default.** Three of 33 entries remove; the rest hide. Removal
  is irreversible in the page's own terms — the element is gone, and a site that
  expects it back gets a dangling reference. Hiding is the conservative action
  and the set uses it unless hiding demonstrably does not work, which is the
  case for overlays that re-show themselves on interaction and for scroll locks
  that live on `<body>`.

## The budgets

`build/qa/perf/generic-set-budgets.json` is **generated** by the checker and
never hand-edited; `--check` diffs it against a fresh measurement, so a
hand-edited number is a number nobody measured.

- **33 rules against a 64-rule budget.** The set costs document-start time on
  *every* page, including pages with no ads. A generic set that grew to
  thousands of rules would be the opposite of the degrade law.
- **~3.3 ms measured key-set build against a 50 ms budget**, on 2 CPUs. The row
  is `trend` class: it records what was observed and never asserts `MET`.

## The no-rules-no-work law

Checked against the host in **both** flag states, not just the default:

- flag off, any rule count ⇒ `observer_installed=false`,
  `generic_set_applies=false`, `cosmetic_enabled=false`;
- flag on, zero rules ⇒ `observer_installed=false` (no rules, no work);
- flag on, rules present ⇒ `observer_installed=true`,
  `generic_set_applies=true`;
- an empty key set is a typed refusal (`empty-rule-set`), not an empty success —
  compiling nothing into something that looks like a key set would let a caller
  install an observer for nothing.

This is what makes the default-off state identical to today's product, and it is
asserted rather than assumed: an earlier version of the checker asserted
`observer_installed=true` at `keyset_rules=1` without turning the flag on, which
is a test that would have failed for a reason unrelated to the law it was
written to check.

## What this document does not claim

No rendered result. `gn` and `ninja` are absent from the environment this was
built in, so nothing here was measured in a browser. The budgets are host-level
measurements of the real key-set builder; the page-level assertions are HG-31.
