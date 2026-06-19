"""Make `src/` importable for tests regardless of pytest version (belt-and-suspenders to pyproject pythonpath)."""
import sys
from pathlib import Path

SRC = str(Path(__file__).parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
