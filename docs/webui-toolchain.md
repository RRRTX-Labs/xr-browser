# The reproducible WebUI toolchain (P7)

The command-registry WebUI (the four views + window-chrome skeleton) is built by
a **reproducible, lock-pinned, CSP-strict toolchain**. This is the "stable for
other tracks" deliverable: P8 (settings) and P13 (XR Panel) add WebUI through
the *same* toolchain, so the build is never re-invented per surface.

## Layout

```
xr-core/ui/
  shell.ts                 esbuild entrypoint (registers the three view elements)
  index.html               the shell — external, integrity-pinned bundle ONLY
  tokens.css               design tokens (RTL-logical only — see rtl_lint)
  tsconfig.json            strict (no `any`, noUnused*, ...) — type-checked by tsc
  palette/                 view #1 — ARIA APG combobox
  shortcut-editor/         view #3 — conflict shown BEFORE binding
  help-index/              view #4 — printable cheatsheet, no coming-soon rails
  BUILD.gn                 farm-integration placeholder (grit lands in P16)
  toolchain/
    package.json           EXACTLY three packages: lit, esbuild, typescript
    package-lock.json      integrity-pinned (the only trusted network input)
    build.mjs              deterministic esbuild bundle (no sourcemap, no clock)
    check-bundle.js        CSP lint on the OUTPUT (no inline JS / eval / network)
```

## The one trusted network input

The only network access the toolchain performs is the lock-pinned install:

```
npm ci --ignore-scripts --no-audit --no-fund
```

- `npm ci` installs *exactly* what `package-lock.json` pins (it fails if the
  lock drifts from `package.json`).
- `--ignore-scripts` runs **no** install script. esbuild's platform binary
  (`@esbuild/linux-x64`) ships as an integrity-pinned *optionalDependency*, so
  nothing is needed from a postinstall — `--ignore-scripts` is both safe and
  correct.
- `lit`, `esbuild`, `typescript` are the **only** packages. Any fourth is a P7
  stop-condition (a new supply-chain edge that has not been reviewed).

If node/npm is absent or the registry is unreachable, the build **SKIPs VISIBLY**
(`build/webui/toolchain.sh` exit 77) and the sources + config still ship — the
UI is not a blocker for the tree. A genuine type / bundle / CSP failure is a
**FAIL** (exit 1), never a skip.

## Determinism (the R1 reproducibility rung)

A WebUI build must be a pure function of (sources, config, toolchain version):

- `esbuild` is pinned (lock) and the bundle disables sourcemaps + legal-comments
  (no source paths, no timestamps).
- `build/webui/repro-check.sh` builds the bundle **twice from the same tree** and
  asserts the outputs (bundle.js + index.html + tokens.css) are **byte-identical**
  (sha256). A divergence FAILs — a non-repro build is not shippable.

This is the "stable" rung that gates later tracks' WebUI builds.

## Gates (all in `tools/run_checks.sh`, P7 section)

| Gate | Command | Law |
|---|---|---|
| tsc strict | `npm ci --ignore-scripts && npx tsc -p ui` | no `any`, no unused, decorators typed |
| deterministic bundle | `node build.mjs` | minified ESM, no sourcemap, no clock |
| CSP on output | `node check-bundle.js` | no inline JS / eval / runtime network / sourcemap |
| repro | `build/webui/repro-check.sh` | two builds byte-identical |
| runtime egress | `tools/csp_lint.py` | no fetch/XHR/WebSocket/eval in `ui/**` + `commands/**` (source) |
| a11y | `tools/a11y_lint.py` | ARIA APG combobox + aria-live empty-state + `:focus-visible` |
| RTL | `tools/rtl_lint.py` | logical-properties-only CSS (no physical left/right) |

## CSP (what the built bundle must survive)

`script-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'`.
Consequences, enforced structurally (source **and** output):

- **No inline `<script>`** — `index.html` loads only the external `bundle.js`.
- **No `eval` / `new Function`** — the minifier's output is re-scanned.
- **No runtime network** — no `fetch` / `XHR` / `WebSocket` in the view sources;
  all command logic goes to the C++ `commands_host` (the host protocol), never
  to a URL.
- **No `sourceMappingURL`** — prod bundle carries no source paths.
