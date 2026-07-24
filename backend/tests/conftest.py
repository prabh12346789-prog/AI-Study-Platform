"""
conftest.py — session-wide test database isolation.

CRITICAL: os.environ["MEMORY_DB_PATH"] is set here at MODULE IMPORT TIME,
before any test module is collected and before any `TestClient(app)` is
instantiated at module level.  This guarantees that:

  1. The FastAPI app's startup hook calls get_engine() with the temp DB path.
  2. All UPSCBooksService / UPSCNotesService sessions use the temp DB.
  3. CLI subprocess tests inherit the env var via os.environ.copy().

Production file: backend/data/memory.sqlite3 is NEVER touched during pytest.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── Ensure src/ is importable ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT))

# ── Session-wide temp database ─────────────────────────────────────────────
# Create once, before any test module is imported.
_TMP_DIR = tempfile.mkdtemp(prefix="upsc_pytest_")
_TEST_DB = os.path.join(_TMP_DIR, "test_memory.sqlite3")

# Point ALL storage calls (app startup, services, CLI subprocesses) at the
# temp DB.  Production memory.sqlite3 is untouched.
os.environ["MEMORY_DB_PATH"] = _TEST_DB

# ── Teardown: delete temp DB when the pytest process exits ─────────────────
@atexit.register
def _remove_temp_db() -> None:
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
