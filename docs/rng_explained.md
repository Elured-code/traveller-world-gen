# Understanding the RNG system

A guide for Python beginners. This document explains how randomness is managed
across the entire Traveller generator — why the design is the way it is, how to
use it correctly when adding new dice rolls, and how the test suite plugs into it.

---

## Why a custom RNG system?

Python's `random` module keeps one shared global state. If two pieces of code both
call `random.randint()`, the order they run in changes every other caller's results.
For a game world generator, that is a problem: we want the same seed to always
produce the same planet.

The solution used here is **injectable RNG**: every generation function accepts an
optional `rng` argument. Pass in a seeded `random.Random` instance and every roll
in that call chain uses it. The instance is isolated — nothing else in the program
touches it — so the seed is perfectly reproducible.

---

## The `_rng` sentinel

Every generation module declares a module-level variable:

```python
import random

_rng: random.Random = random   # starts as the global random module
```

The sentinel starts as `random` (the *module* itself, not an instance). Python's
`random` module exposes `randint`, `choice`, etc. directly — so `_rng.randint(1,6)`
works whether `_rng` is the module or a `random.Random` instance.

This means that until someone passes an explicit `rng` to a public function, all
dice rolls go through the global module's shared state — exactly like plain old
`random.randint()`. No behaviour change for code that does not opt in.

---

## How public functions use the sentinel

Every public entry point resolves the RNG at the top:

```python
def generate_world(seed=None, rng=None):
    rng = rng if rng is not None else _rng
    # ... all internal rolls use rng ...
```

If the caller passes `rng=some_instance`, that instance is used. If not, the
function falls back to `_rng` (which is the global `random` module by default).
This keeps the function safe for both uses: seeded deterministic calls *and* quick
interactive use that relies on the global state.

---

## `generate_full_system` always creates a fresh RNG

The top-level entry point is special:

```python
def generate_full_system(name=None, seed=None, rng=None, ...):
    seed = seed or secrets.token_hex(4)
    if rng is None:
        rng = random.Random(seed)
    # propagates rng to every sub-generator
```

A `random.Random(seed)` instance is **completely isolated** from the global
`random` module. It has its own internal state; calls to `random.seed()` elsewhere
in the program have no effect on it, and vice versa.

By storing the seed in `TravellerSystem.seed`, every system is reproducible:

```python
system1 = generate_full_system("Homeworld", seed="a3b1c9d0")
system2 = generate_full_system("Homeworld", seed="a3b1c9d0")
assert system1.to_dict() == system2.to_dict()  # always true
```

---

## Private helpers take `rng` directly

After the refactor completed in session 116, private helpers (functions whose
names start with `_`) no longer read `_rng` themselves. Instead they receive
`rng` as an explicit argument:

```python
def _secondary_population(max_pop: int, rng: random.Random) -> int:
    if max_pop <= 0:
        return 0
    if rng.randint(1, 6) >= 5:
        return 0
    return rng.randint(1, max_pop)
```

This makes the call chain easy to follow: trace `rng` from the public entry
point down through every helper, and you can reconstruct the exact sequence of
dice rolls that produced a world.

---

## The dice-ordering rule

> **New dice rolls belong at the end of the pipeline.**

Every roll in a module is part of a sequence. Inserting a roll in the middle
shifts all subsequent results for every existing seed — effectively changing
the output of every world ever generated. To avoid that, new optional features
always append rolls after existing ones rather than inserting them in the middle.

`attach_detail()` appends the biological rolls (`_apply_biomass`) at the very
end, after every SAH and social roll, specifically for this reason.

---

## The `global _rng` pattern (pre-session-116)

Older code — and you may still encounter it in non-generation modules — used a
different pattern:

```python
def some_function(rng=None):
    global _rng                   # ← this pattern is now removed from generation modules
    if rng is not None:
        _rng = rng
    # ... rolls used _rng ...
```

This pattern mutates shared module state, which is not thread-safe: if two
threads call `some_function(rng=rng_a)` and `some_function(rng=rng_b)`
concurrently, one thread's `_rng` may overwrite the other's.

The current pattern (`rng = rng if rng is not None else _rng`) reads `_rng`
once and stores the result in a local variable — safe for concurrent calls.

---

## How the tests use the RNG system

Tests use three approaches, depending on what they need to verify:

### 1. Patch the global module

For tests that call a public function without an explicit `rng`:

```python
def test_atmosphere_for_size_2(self):
    with patch("traveller_world_gen.random.randint", return_value=6):
        atm = generate_atmosphere(2)
    assert atm == ...
```

Because `_rng` defaults to the `random` module, patching
`traveller_world_gen.random.randint` intercepts every roll made through `_rng`.

### 2. Seed the global module

For tests that run a full pipeline and need reproducible multi-roll sequences:

```python
def test_system_always_produces_some_output(self):
    for seed in range(50):
        random.seed(seed)
        system = generate_full_system("Test", seed=seed)
        assert system.mainworld is not None
```

`random.seed(seed)` resets the global module's state. Combined with the
`conftest.py` fixture (see below), each test starts from a known global state.

### 3. Pass an explicit `random.Random`

For fine-grained deterministic tests of private helpers:

```python
def test_independent_government_is_non_negative(self):
    for seed in range(50):
        gov = _twd._independent_government(pop=3, rng=random.Random(seed))
        assert gov >= 0
```

Using `random.Random(seed)` avoids touching the global module at all — the
test is completely self-contained.

---

## The `conftest.py` fixture

`conftest.py` in the project root defines an `autouse=True` fixture:

```python
@pytest.fixture(autouse=True)
def reset_module_rngs():
    for mod in _modules:
        mod._rng = random          # reset before each test
    yield
    for mod in _modules:
        mod._rng = random          # reset after each test
```

The fixture runs before and after **every** test, whether or not the test asked
for it. Before the test, it restores every module's `_rng` to the global
`random` module. After the test, it does the same.

Why is this needed? If a test calls `generate_world(rng=random.Random(42))`,
the old `global _rng` pattern would have replaced `traveller_world_gen._rng`
with that seeded instance. The *next* test's call to `random.seed(99)` would
then have no effect — `_rng` no longer refers to the global module. The fixture
prevents that cross-contamination.

Even with the new pattern (which no longer mutates `_rng`), the fixture is kept
to remain compatible with any external code that still writes to `mod._rng`
directly, and to make the test environment's baseline explicit.

---

## Quick reference

| Situation | What to do |
|-----------|-----------|
| Adding a new dice roll inside an existing private helper | Use the `rng` parameter already present |
| Adding a new public function | Add `rng: Optional[random.Random] = None` + `rng = rng if rng is not None else _rng` |
| Adding a new private helper | Accept `rng: random.Random` as a required argument (no default) |
| Adding a roll at the end of the pipeline | Append after all existing rolls in the function |
| Writing a unit test for a private helper | Pass `rng=random.Random(seed)` explicitly |
| Writing an integration test | Use `random.seed(seed)` OR pass `rng=random.Random(seed)` to the public entry point |
| `generate_full_system` | Always creates its own `random.Random(seed)` — no external state leaks in |
