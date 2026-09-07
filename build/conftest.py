"""pytest conftest for the build-tool suites under build/*/tests/.

Adds every build subdir to sys.path so tests import the tools the same way
the ./scripts/build dispatcher runs them (stdlib-first, no package install).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in [ROOT, ROOT / "patching", ROOT / "gn", ROOT / "branding",
          ROOT / "sbom", ROOT / "signing", ROOT / "farm", ROOT / "toolchain"]:
    sys.path.insert(0, str(p))
