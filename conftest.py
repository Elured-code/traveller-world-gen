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

# Insert the project root (the directory containing this file) at the
# front of sys.path.  This makes the following imports work from any
# test file regardless of the working directory pytest is invoked from:
#
#   from traveller_world_gen import generate_world
#   from shared.helpers import ok, error
#
sys.path.insert(0, os.path.dirname(__file__))


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
