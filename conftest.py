"""
conftest.py
===========
pytest configuration for the traveller-world-gen project.

Generation modules are installed as the ``traveller_gen`` package (pip install -e .)
so no sys.path manipulation is needed for them.  azure-api/ and fastapi/ are still
added so that test files can import function_app, shared.helpers, and the fastapi app.
"""
import random
import sys
import os

import pytest

# Insert azure-api/ and fastapi/ into sys.path so that test files can import
# all API layers without special setup:
#
#   from function_app import ...          # azure-api/
#   from shared.helpers import ok, error  # azure-api/shared/
#   from app import app                   # fastapi/ (flat module)
#   from helpers import ok, error         # fastapi/ (flat module)
#
# Generation modules (traveller_gen.*) are importable without any path hack
# because they are installed via ``pip install -e .``.
_root = os.path.dirname(__file__)
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
    from traveller_gen import traveller_hydro_detail
    from traveller_gen import traveller_belt_physical
    from traveller_gen import traveller_world_physical
    from traveller_gen import traveller_world_gen
    from traveller_gen import traveller_stellar_gen
    from traveller_gen import traveller_orbit_gen
    from traveller_gen import traveller_moon_gen
    from traveller_gen import traveller_world_detail
    from traveller_gen import traveller_world_population_detail
    from traveller_gen import traveller_world_government_detail
    from traveller_gen import traveller_world_law_detail
    from traveller_gen import traveller_world_tech_detail
    from traveller_gen import traveller_world_culture_detail
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
        traveller_world_population_detail,
        traveller_world_government_detail,
        traveller_world_law_detail,
        traveller_world_tech_detail,
        traveller_world_culture_detail,
    ]

    for mod in _modules:
        mod._rng = random  # type: ignore[attr-defined]  # pylint: disable=protected-access

    yield

    for mod in _modules:
        mod._rng = random  # type: ignore[attr-defined]  # pylint: disable=protected-access
