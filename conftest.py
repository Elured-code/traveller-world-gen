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

# Append (not insert at position 0) azure-api/ and fastapi/ to sys.path so
# that test files can import all API layers without special setup:
#
#   from function_app import ...          # azure-api/
#   from shared.helpers import ok, error  # azure-api/shared/
#   from app import app                   # fastapi/ (flat module)
#   from helpers import ok, error         # fastapi/ (flat module)
#
# Generation modules (traveller_gen.*) are importable without any path hack
# because they are installed via ``pip install -e .``, which appends src/ to
# sys.path via a .pth file before conftest.py ever runs. Appending here (not
# inserting at position 0) keeps that src/ entry ahead of azure-api/ in
# sys.path, so a leftover azure-api/traveller_gen/ build artifact from a
# local ``scripts/prepare_azure.sh`` run can never shadow the real source
# package during pytest (issue #172).
_root = os.path.dirname(__file__)
sys.path.append(os.path.join(_root, "azure-api"))
sys.path.append(os.path.join(_root, "fastapi"))

# Fail loudly if something still manages to shadow the source package,
# instead of silently testing against a stale mirror (issue #172).
import traveller_gen  # pylint: disable=wrong-import-position

_expected_src = os.path.join(_root, "src", "traveller_gen")
_actual_src = os.path.dirname(traveller_gen.__file__)
assert os.path.samefile(_actual_src, _expected_src), (
    f"traveller_gen resolved to {_actual_src!r}, not {_expected_src!r}. "
    "A stale build artifact (e.g. azure-api/traveller_gen/ from "
    "scripts/prepare_azure.sh) is likely shadowing the real source package "
    "on sys.path -- delete it and re-run pytest."
)


@pytest.fixture(autouse=True)
def reset_module_rngs():  # pylint: disable=too-many-locals
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
    from traveller_gen import traveller_world_atmosphere_detail
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
        traveller_world_atmosphere_detail,
    ]

    for mod in _modules:
        mod._rng = random  # type: ignore[attr-defined]  # pylint: disable=protected-access

    yield

    for mod in _modules:
        mod._rng = random  # type: ignore[attr-defined]  # pylint: disable=protected-access
