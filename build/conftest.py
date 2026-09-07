"""pytest conftest for the build-tool suites under build/*/tests/.

Adds every build subdir to sys.path so tests import the tools the same way
the ./scripts/build dispatcher runs them (stdlib-first, no package install).

P4-T0.1: surfaces the optional-external-tool SKIP policy in the run summary.
A skipped external-tool test is visible here (L6 — never silent): the suite
prints one SKIP row per missing tool even if no test that needs it runs.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in [ROOT, ROOT / "patching", ROOT / "gn", ROOT / "branding",
          ROOT / "sbom", ROOT / "signing", ROOT / "farm", ROOT / "toolchain",
          ROOT / "upstream", ROOT / "spike"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_terminal_summary(terminalreporter):
    """Print the external-tool SKIP table at the end of every run."""
    try:
        import skip_policy
    except ImportError:  # policy module missing => nothing to report
        return
    rows = skip_policy.collect_skips()
    if not rows:
        return
    terminalreporter.write_sep("=", "optional external tools (SKIP policy)")
    for row in rows:
        terminalreporter.write_line(skip_policy.summary_line(row))
    terminalreporter.write_line(
        f"{len(rows)} external tool(s) absent on this host: the dependent "
        f"tests SKIP with the reason above (never a silent pass).")
