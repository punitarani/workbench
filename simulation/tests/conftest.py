import sys
from pathlib import Path

# Share test fixtures (payload samples, coherent world logs) across packages.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "workbench" / "tests"))
