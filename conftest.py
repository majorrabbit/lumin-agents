"""
Root pytest conftest.

Adds the lumin-agents/ directory to sys.path so tests can import from
shared/ regardless of where pytest is invoked from.
"""
import os
import sys

# Insert the repo root so `import shared.secrets` etc. always resolves.
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)
