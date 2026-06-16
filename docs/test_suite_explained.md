# Understanding the test suite

A guide for Python beginners. This document explains how the project's tests are
organised, what strategies they use, and how to run and extend them.

---

## Running the tests

```bash
.venv/bin/pytest tests/ -q
```

The `-q` flag gives compact output: one dot per passing test, one letter per
failing test, then a summary line. As of session 116, the suite has **2044 tests**
(2044 passed, 1 skipped). All must pass before merging.

To run a single file or class:

```bash
.venv/bin/pytest tests/test_traveller_world_gen.py -q
.venv/bin/pytest tests/test_traveller_world_gen.py::TestAssignTradeCodes -q
```

---

## What `conftest.py` does

`conftest.py` in the project root is automatically loaded by pytest before any
test runs. It does two things:

### 1. Fixes the import path

```python
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "azure-api"))
sys.path.insert(0, os.path.join(_root, "fastapi"))
```

Tests in `tests/` can import `traveller_world_gen`, `function_app`,
`shared.helpers`, and `app` (FastAPI) without any manual path manipulation.

### 2. Resets the RNG sentinels before and after every test

```python
@pytest.fixture(autouse=True)
def reset_module_rngs():
    for mod in _modules:
        mod._rng = random
    yield
    for mod in _modules:
        mod._rng = random
```

`autouse=True` means this fixture runs for every test without needing to be
listed in the test's argument list. It ensures that each test starts with every
module's `_rng` pointing at the global `random` module. Without this, a test
that passes a seeded `random.Random` instance to a generator would leave that
instance in the module's `_rng`, and subsequent tests' `random.seed()` calls
would have no effect on it.

See [rng_explained.md](rng_explained.md) for the full RNG design.

---

## Test file overview

| File | What it tests | Tests |
|------|--------------|-------|
| `test_traveller_world_gen.py` | Mainworld generation: every step from size to trade codes; full system generation; secondary world SAH, social, and classification; moons; body names; property-based invariants | ~950 |
| `test_world_physical.py` | Physical characteristics — diameter, density, gravity, axial tilt, day length, tidal lock, seismic stress | ~300 |
| `test_belt_physical.py` | Belt physical detail — span, composition, bulk, resource rating, significant bodies | ~150 |
| `test_hydro_detail.py` | Hydrographic surface detail — liquid percentages and basin depths | ~29 |
| `test_biomass.py` | Biomass, biocomplexity, sophont checks, biodiversity, compatibility ratings | ~200 |
| `test_habitability.py` | Habitability rating — each DM contributor and boundary cases | ~50 |
| `test_moon_gen.py` | Moon counts, size codes, rings, orbit placement | ~100 |
| `test_orbit_gen.py` | Orbit slot placement, habitable zones, MAO, HZCO | ~80 |
| `test_system_roundtrip.py` | `to_dict()` / `from_dict()` round-trip for all data structures | ~50 |
| `test_hypothesis.py` | Property-based tests using Hypothesis — range invariants over millions of seeds | ~30 |
| `test_fastapi_app.py` | FastAPI server: all 11 endpoints, error handling, rate limiting | ~80 |
| `test_function_app.py` | Azure Functions: all endpoints using azure-functions stubs | ~80 |
| `test_tech_detail.py` | Technology level detail (TL sub-components) | ~30 |

---

## The three test strategies

### Strategy 1: Patch the dice

Most unit tests isolate a single function by replacing the underlying
`randint` call with a fixed value:

```python
from unittest.mock import patch

def test_atmosphere_for_size_6(self):
    # Force both dice rolls to 3 (total = 6); no DM for size 6 → atmosphere 6
    with patch("traveller_world_gen.random.randint", return_value=3):
        atm = generate_atmosphere(6)
    assert atm == 6
```

`patch("traveller_world_gen.random.randint", return_value=3)` replaces every
call to `randint` *inside* `traveller_world_gen` for the duration of the `with`
block. When the block exits, the real function is restored.

`side_effect` lets you give a *sequence* of return values — useful when a
function makes more than one dice roll:

```python
with patch("traveller_world_gen.random.randint", side_effect=[6, 6]):
    # first roll returns 6, second roll returns 6
    ...
```

Some tests patch `traveller_world_gen.roll` instead. `roll()` is the project's
wrapper around `randint` that applies a DM and clamps the result — patching it
is cleaner when you want to control the *post-DM* value rather than the raw dice.

### Strategy 2: Seed the global random

For tests that need a realistic multi-roll sequence (e.g. testing that a full
world generation stays within valid ranges), the global `random` module is
seeded directly:

```python
def test_trade_codes_always_valid(self):
    valid = {tc.value for tc in TradeCode}
    for seed in range(200):
        random.seed(seed)
        world = generate_world()
        for code in world.trade_codes:
            assert code in valid
```

`random.seed(seed)` makes the *global* `random` module deterministic. Because
`_rng` defaults to `random` (the module), every roll inside `generate_world()`
is deterministic for that seed. The `conftest.py` fixture resets this state
between tests so they do not interfere with each other.

### Strategy 3: Pass an explicit `random.Random`

For tests of private helpers or integration flows that must not touch the global
state, an isolated `random.Random(seed)` is passed directly:

```python
def test_independent_government_is_non_negative(self):
    import traveller_world_detail as _twd
    for seed in range(50):
        gov = _twd._independent_government(pop=3, rng=random.Random(seed))
        assert gov >= 0
```

This is the cleanest approach — the test does not depend on global state at all.
It is the preferred strategy for any new tests added to the suite.

---

## Property-based tests (Hypothesis)

`test_hypothesis.py` uses the [Hypothesis](https://hypothesis.readthedocs.io/)
library to run tests against *randomly generated inputs* rather than hand-picked
cases:

```python
@given(st.integers(min_value=0, max_value=2**31 - 1))
def test_size_in_range(self, seed):
    w = generate_world(seed=seed)
    assert 0 <= w.size <= 10
```

Hypothesis generates hundreds of seeds per test run and, if it finds a
counterexample, shrinks it to the smallest failing input and reports it. These
tests catch edge cases that no hand-picked list of seeds would ever hit.

Property-based tests run the same command as the rest of the suite. They are
slightly slower than unit tests — each `@given` test runs ~100 examples by
default — but they run in well under a second each.

---

## Round-trip tests

`test_system_roundtrip.py` checks that every data structure serialises to a
dict and deserialises back to an identical object:

```python
def test_star_round_trip(self):
    star = Star.from_dict(_make_star_dict())
    d = star.to_dict()
    star2 = Star.from_dict(d)
    assert star2.designation == star.designation
    assert star2.spectral_type == star.spectral_type
    ...
```

These tests protect against `to_dict()` and `from_dict()` falling out of sync
when new fields are added to a dataclass. If you add a field to `World` and
forget to update `from_dict()`, a round-trip test will fail.

---

## API tests

`test_fastapi_app.py` and `test_function_app.py` test the HTTP layer without a
running server.

**FastAPI** uses Starlette's `TestClient`:

```python
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_get_world(self):
    response = client.get("/api/world/Homeworld?seed=abc123")
    assert response.status_code == 200
    data = response.json()
    assert data["seed"] == "abc123"
```

`TestClient` drives the full ASGI stack in-process. No network is involved — the
test is as fast as a regular function call.

**Azure Functions** uses `azure.functions` stubs defined in the same test file
(because the real Azure SDK is a cloud service and cannot run locally in a unit
test). The stubs mimic the `HttpRequest` and `HttpResponse` classes so that
`function_app.py` sees the same interface it would in production.

For both API test files, calls to `generate_system_from_map()` are patched to
avoid live HTTP requests to the TravellerMap API:

```python
with patch("app.generate_system_from_map", return_value=mock_system):
    response = client.get("/api/map/system?hex=0101&sector=Spinward+Marches")
```

---

## How to add a new test

1. **Decide which file it belongs in.** Each file tests one module or layer.
   Tests for `traveller_world_gen.py` go in `test_traveller_world_gen.py`, etc.

2. **Choose a strategy.** If the function makes one or two rolls and you need to
   check the DM arithmetic, patch `random.randint` (Strategy 1). If you need a
   realistic multi-roll sequence, pass `rng=random.Random(seed)` (Strategy 3).
   Only use `random.seed()` (Strategy 2) when the function you're testing does
   not accept an explicit `rng` argument.

3. **Group into a class.** All tests in this project live inside `class Test...`
   blocks. Name the class after the function or feature under test:
   `TestGenerateBiomass`, `TestLawLevelDetail`, etc.

4. **Keep each test focused.** Test one fact per test method. If the method
   body has more than one `assert`, ask whether it should be split into two tests.

5. **Run pylint on the test file.** The project target is 10.00/10:
   ```bash
   .venv/bin/pylint tests/test_yourfile.py
   ```

---

## Test count history

| Session | Tests | Notes |
|---------|-------|-------|
| ≤ 100 | ~1400 | Pre-WBH physics |
| 101 | 1551 | World physical detail |
| 109 | 1884 | Belt physical + moon gen |
| 114 | 2013 | Secondary world SAH + social |
| 116 | 2044 | RNG threading + hzco removal; test updates to match refactored private helper signatures |
