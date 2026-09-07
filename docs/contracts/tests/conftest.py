import sys
from pathlib import Path
# Make the xr-core fakes importable for parity/determinism tests.
FAKES = Path(__file__).resolve().parents[4] / "xr-core" / "fakes"
if str(FAKES) not in sys.path:
    sys.path.insert(0, str(FAKES))
