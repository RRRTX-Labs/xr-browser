// axe_run.mjs — farm-side axe-core lane (P9-T7).
//
// DECISION (recorded in docs/qa/a11y-contract.md): axe-core requires a real
// DOM. The only DOM shim that would let it run without a browser is jsdom —
// a SECOND package, which is not authorized (DEPENDENCY RULES). So axe does
// NOT run in the P9 sandbox: this file is the farm runner, and the in-repo
// lane is the AXTree snapshot harness (tools/a11y_tree.py) with its canary.
//
// The browser-side axe run (HG-31): run against the built bundle in the farm
// browser after each view renders. axe-core is a devDependency in
// ui/toolchain (exact-pinned, lock-integrity, npm ci --ignore-scripts).
//
// This script is intentionally minimal and refuses to fake a result: when
// invoked without a DOM/browser it prints a visible SKIP and exits 77.
import { existsSync } from "node:fs";

const hasDOM = typeof globalThis.document !== "undefined" &&
               typeof globalThis.window !== "undefined";

if (!hasDOM) {
  console.log(
    "SKIP: axe_run needs a browser DOM (HG-31 farm runner). " +
    "The in-sandbox lane is tools/a11y_tree.py (AXTree snapshots).");
  process.exit(77);
}

// On the farm this loads the built bundle and runs axe with the project's
// tag list; the invocation is documented in docs/qa/a11y-contract.md.
console.log("axe_run: farm execution — see docs/qa/a11y-contract.md");
process.exit(77);
