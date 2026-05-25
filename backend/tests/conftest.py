"""Shared test fixtures and configuration for the backend test suite.

All tests are pure unit tests (no database, no HTTP client).
If integration tests are added later, add async/session fixtures here.
"""
import os
import sys

# Ensure the backend/app package is importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set a stable SECRET_KEY for tests so Settings() never warns or raises.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
