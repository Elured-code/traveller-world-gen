"""
conftest.py
===========
pytest configuration for the traveller-world-gen project.

Adds the project root to sys.path so that test files in the tests/
subdirectory can import traveller_world_gen and shared.helpers without
needing any special setup.  pytest discovers this file automatically.
"""
import random
import sys
import os

import pytest

# Insert the project root, azure-api/, and fastapi/ into sys.path so that
# test files in the tests/ subdirectory can import all layers without setup:
#
#   from traveller_world_gen import generate_world   # project root
#   from function_app import generate_world_card     # azure-api/
#   from shared.helpers import ok, error             # azure-api/shared/
#   from app import app                              # fastapi/
#   from helpers import ok, error                    # fastapi/ (flat module)
#
# Note: fastapi/ uses a flat helpers.py (not shared/) to avoid the
# "from shared.helpers import" naming conflict with azure-api/shared/.
_root = os.path.dirname(__file__)
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "azure-api"))
sys.path.insert(0, os.path.join(_root, "fastapi"))


@pytest.fixture(autouse=True)
def reset_module_rngs():
    """Reset every generation module's _rng sentinel to the global random
    module before each test so that random.seed() calls in tests work exactly
    as they did before injectable RNG was added (issue #42).

    Without this fixture, a test that calls generate_world(rng=rng) leaves the
    module-level _rng pointing at an isolated random.Random instance; the next
    test's random.seed() call then has no effect on that instance, causing
    order-dependent test failures.
    """
    # pylint: disable=import-outside-toplevel
    import traveller_hydro_detail
    import traveller_belt_physical
    import traveller_world_physical
    import traveller_world_gen
    import traveller_stellar_gen
    import traveller_orbit_gen
    import traveller_moon_gen
    import traveller_world_detail
    # pylint: enable=import-outside-toplevel

    _modules = [
        traveller_hydro_detail,
        traveller_belt_physical,
        traveller_world_physical,
        traveller_world_gen,
        traveller_stellar_gen,
        traveller_orbit_gen,
        traveller_moon_gen,
        traveller_world_detail,
    ]

    for mod in _modules:
        mod._rng = random  # type: ignore[attr-defined]  # pylint: disable=protected-access

    yield

    for mod in _modules:
        mod._rng = random  # type: ignore[attr-defined]  # pylint: disable=protected-access
