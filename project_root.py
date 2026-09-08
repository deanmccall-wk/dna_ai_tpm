"""Project root path and sys.path bootstrap.

Import this module before any project-local imports to ensure the project
root is on sys.path. Works on macOS, Linux, and Windows.

Usage (first line of every entry-point script):
    import project_root  # noqa: F401  -- adds project root to sys.path
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)