"""Pytest configuration and shared fixtures.

This file is automatically discovered by pytest and runs before any test files.
We use it to mock duckdb module globally to prevent segfaults in tests.
"""

import sys
from unittest.mock import MagicMock

# Mock duckdb module before any imports
# This ensures that when database modules are imported, they will use the mock
# instead of loading the real DuckDB C extension library
sys.modules["duckdb"] = MagicMock()
