import sys
from pathlib import Path

# Shared fixture modules (payload samples, world-log fixtures) importable
# from every test package without per-directory path hacks.
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
