# Scriptlets (P12)

**Execution is OFF.** `xr_shield_scriptlets` defaults to `false`, no interpreter
is wired into the host path, and the ABPF validator
(`xr-core/renderer/cosmetic/abpf/abpf.cc`) **refuses** `$ext-…` directives rather
than accepting and ignoring them — accepting would imply the scriptlet runs, and
an implied capability nobody can see is how a phase ships more than it claims to.

What exists in this phase is the **registry** and the **validator**: a closed
admitted set with a capability note and a degrade case per entry, and a degrade
corpus proving each one is disable-able individually and that disabling it
leaves the page's structure intact.

`tools/scriptlet_registry_check.py` enforces per entry: a capability note, a
degrade case, a refusal case, a doc line, a `path:line@vendored` source
citation, an explicit `page_modifying` boolean, and **no** main-world
capability. A missing one is a FAIL.

## Capability classes

| capability | what it can do | why it is bounded |
| --- | --- | --- |
| `property-read` | traps a read on an object the page already handed us | takes a property name, arity 1 |
| `property-write` | traps or pins a write | arity ≤ 2; a scriptlet taking an expression would be an interpreter |
| `dom-attribute` | adds, sets or removes attributes | names come from a closed set, never a selector built from page content |
| `timer` | suppresses a matching `setTimeout` | the pattern is a literal substring, not a regex — a regex engine on page input is a ReDoS channel |
| `eval-guard` | neutralises `eval` | arity 0, so there is no page-controlled input to bound |
| `api-guard` | disables a named API | arity 0 |
| `storage` | deletes matching cookies | arity 1, bounded name pattern; behind the flag twice over because it can break a login |

No entry has a main-world capability. A scriptlet that needs the page's own
realm is a code-execution channel, and this phase does not ship one.

## Admitted set

### abort-on-property-read

Throws on a named property read so a script's ad call fails. Does not modify the
DOM and needs no main-world access: it is a property trap on an object the page
already handed us. Arity 1. Source
`src/scriptlets/abort_on_property_read.rs:18-44@vendored`. Not page-modifying.

### abort-on-property-write

The write-side trap. Same capability class as the read variant and the same
reason it needs no main world. Arity 1. Source
`src/scriptlets/abort_on_property_write.rs:16-39@vendored`. Not page-modifying.

### set-constant

Pins a property to a constant. Bounded by arity 2 (path, value): a scriptlet
that took an arbitrary expression would be an interpreter, and an interpreter in
the renderer is a code-execution channel. Source
`src/scriptlets/set_constant.rs:20-52@vendored`. Not page-modifying.

### remove-attr

**Page-modifying.** Removes attributes, which is how a soft wall's
`overflow:hidden` on `<body>` gets lifted. Labelled page-modifying in the event
schema so the Observatory does not report it as a blocked request — an injected
or removed element is not a blocked request. Attribute names come from a closed
set, never a selector built from page content. Arity 2. Source
`src/scriptlets/remove_attr.rs:22-58@vendored`.

### remove-class

**Page-modifying.** Strips classes so a wall's styling stops applying. The DOM
structure is unchanged — only the class attribute is — which is what the degrade
corpus asserts on the model. Arity 2. Source
`src/scriptlets/remove_class.rs:19-47@vendored`.

### set-attr

**Page-modifying.** Sets an attribute to a bounded literal. The value length is
capped, because an unbounded value is a way to inject markup through an
attribute. Arity 3. Source `src/scriptlets/set_attr.rs:21-55@vendored`.

### json-prune

Removes keys from a parsed JSON response before the page reads it. Depth is
bounded (`kMaxJsonDepth`) so a hostile document cannot make the walk unbounded.
Arity 2. Source `src/scriptlets/json_prune.rs:24-61@vendored`. Not
page-modifying.

### no-setTimeout-if

Suppresses a `setTimeout` whose callback matches a bounded pattern. The pattern
is a literal substring, **not** a regular expression: a regex engine driven by
page-controlled input is a ReDoS channel, and the degrade law is that cosmetic
filtering must never make a page slower. Arity 2. Source
`src/scriptlets/no_set_timeout_if.rs:26-64@vendored`. Not page-modifying.

### prevent-setTimeout

The alias uBO lists use. Same capability and the same literal-substring
restriction as `no-setTimeout-if`. Arity 2. Source
`src/scriptlets/prevent_set_timeout.rs:25-60@vendored`. Not page-modifying.

### noeval

Neutralises `eval` on the page's own realm object. Arity 0: it takes no
argument, so there is no page-controlled input to bound. Source
`src/scriptlets/noeval.rs:14-33@vendored`. Not page-modifying.

### nowebrtc

Disables `RTCPeerConnection`, the local-IP leak channel. Arity 0. Source
`src/scriptlets/nowebrtc.rs:12-30@vendored`. Not page-modifying.

### cookie-remover

**Page-modifying.** Deletes cookies matching a bounded name pattern. Storage
access is the reason this one is behind the flag twice over — it can break a
site's login, which is a user-visible failure and not a cosmetic one. Arity 1.
Source `src/scriptlets/cookie_remover.rs:23-57@vendored`.

## Refused, and why

Recorded so the refusal is visible rather than implicit. A registry that simply
omitted these would leave a future reader guessing whether the omission was a
decision or an oversight.

- **eval-defuser** — requires main-world execution to replace the page's own
  `eval` binding. `main_world_permitted` is false, so admitting it would be a
  claim the implementation cannot back.
- **set-attr-defuser** — takes a selector built from page content. A selector
  derived from the document is an injection channel; every admitted attribute
  scriptlet takes its names from a closed set instead.
- **trusted-types** — installs a Trusted Types policy on the page's realm, which
  is main-world state the renderer must not own.
- **prevent-fetch** — intercepts network requests. That is the network layer's
  job (P5/P6), and a cosmetic scriptlet performing a network action would put
  request interception in the renderer where no policy object governs it.

## The degrade law, and what it is asserted on

`docs/contracts/cosmetic-scriptlet-degrade.json` carries 312 cases over 12
synthetic pages and 12 scriptlets. Every case is a **DOM-model fixture**, and
`surface: model` is on the document and on every case. The model result is not a
page result, and the file says so on every line rather than once in a header,
because a model result read as a page result is exactly the claim this phase is
graded on.

Per scriptlet the corpus proves:

- **disable-able individually** — one case per page with the scriptlet disabled,
  asserting the page renders the same structure;
- **structure preserved when enabled** — node count and text length are
  unchanged; classes and attributes are what a scriptlet may change. A scriptlet
  that removes *nodes* is doing DOM removal, which is the cosmetic `remove`
  action's job and is labelled page-modifying;
- **refusal path** — a bad arity is refused and the page is untouched, so a
  malformed instruction cannot leave the page in a state neither the list nor
  the user asked for;
- **failure degrades to inert** — one case per page where the scriptlet raises,
  asserting the structure is intact.

The real-engine and real-Blink measurements are a hosted `core-hardening`-style
row where the toolchain exists, and an explicit farm row where Blink is needed.
Nothing in this document claims a rendered result: `gn` and `ninja` are absent
from the environment this was built in.
