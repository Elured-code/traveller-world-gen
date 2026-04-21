"""
conftest.py
===========
pytest configuration for the traveller-world-gen project.

Adds the project root to sys.path so that test files in the tests/
subdirectory can import traveller_world_gen and shared.helpers without
needing any special setup.  pytest discovers this file automatically.
"""
import sys
import os

# Insert the project root (the directory containing this file) at the
# front of sys.path.  This makes the following imports work from any
# test file regardless of the working directory pytest is invoked from:
#
#   from traveller_world_gen import generate_world
#   from shared.helpers import ok, error
#
sys.path.insert(0, os.path.dirname(__file__))
