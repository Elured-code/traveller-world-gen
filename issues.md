# Pending Issues — Code Quality and Readability

Identified in session 113 review of generation modules. All candidates for v1.5.0.

---

## Issue 1 — Replace anonymous tuples in lookup tables with NamedTuple

**Files:** `traveller_world_gen.py`, `traveller_orbit_gen.py`

Several tables store multi-column data as anonymous tuples whose meaning is only
explained in a comment above the table. For example, `_NHZ_HOT_A` and similar
tables use 5-tuples:

```python
# (atm_code, base_exotic_key, irritant_exotic_key, star, dagger)
4: (10, 3, 2, True, False),
```

And `_EXOTIC_SUBTYPE_TABLE` uses 4-tuples:

```python
# (subtype_code, type_name, pressure_min_bar, pressure_span_bar)
6: ("6", "Standard", 0.70, 0.79),
```

Replace with `NamedTuple` (or `@dataclass(frozen=True)`) so call sites use
`entry.atm_code` instead of `entry[0]`, removing the need for positional
unpacking comments and enabling useful type-checking.

**Risk:** Low — structural change to table definitions; callers switch from index
access to attribute access.

---

## Issue 2 — Align `roll()` function signatures across modules

**Files:** `traveller_world_gen.py`, `traveller_stellar_gen.py`,
`traveller_orbit_gen.py`, `traveller_world_physical.py`

Every module defines its own `roll()` tied to its local `_rng` sentinel — that
is by design. However the signatures are inconsistent:

| Module | Signature |
|--------|-----------|
| `traveller_world_gen.py` | `roll(num_dice, modifier=0)` |
| `traveller_stellar_gen.py` | `roll(n, dm=0)` |
| `traveller_orbit_gen.py` | `roll(n, dm=0)` |
| `traveller_world_physical.py` | `_roll(n, dm=0)` (private) |

`traveller_world_gen.py` also has `_dice(num)` (unclamped) while
`traveller_stellar_gen.py` has named `d3()` and `d10()` helpers that do not
exist elsewhere.

Pick one canonical set of names (`n`/`dm`, public `roll`, named die-type helpers)
and apply consistently across all modules.

**Risk:** None — rename only; no logic change.

---

## Issue 3 — Modernise typing imports to Python 3.11 native syntax

**Files:** `traveller_orbit_gen.py` (and any others still using `typing.Dict`,
`typing.List`, `typing.Tuple`)

```python
# Before
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

# After
from typing import Optional, TYPE_CHECKING
# use dict[...], list[...], tuple[...] directly
```

`traveller_stellar_gen.py` and `traveller_world_physical.py` already use the
modern forms. Make this consistent across all modules.

**Risk:** None — cosmetic.

---

## Issue 4 — Remove `global _rng` side-effect from `roll_eccentricity` / `roll_inclination`

**File:** `traveller_orbit_gen.py`

These two public functions use `global _rng; if rng is not None: _rng = rng`
inline, which is a different pattern from every other module's public entry
point. Calling `roll_eccentricity(rng=r)` has a persistent side effect on the
module's `_rng` even though the function name implies a pure calculation.

Move the `global _rng` update to the higher-level `generate_*()` entry points
that call these functions, or make them accept the rng instance directly without
storing it at module level.

**Risk:** Medium — touches the injectable RNG logic exercised by the test suite.
Verify RNG chain is unchanged after refactor.

---

## Issue 5 — Replace if-chain dispatch in `temperature_category` and `starport_class_from_roll` with table-driven lookup

**File:** `traveller_world_gen.py`

These two functions use cascading `if/return` chains while every other mapping
in the codebase uses dict or threshold-list lookups. For example,
`_COMPOSITION_THRESHOLDS` in `traveller_world_physical.py` uses
`[(upper_bound, label)]` pairs iterated with a loop.

Applying the same pattern here is more consistent with the module's own style
and makes the table data visible to tests or other callers without calling the
function:

```python
_TEMPERATURE_THRESHOLDS = [(2, "Frozen"), (4, "Cold"), (9, "Temperate"), (11, "Hot")]

def temperature_category(modified_roll: int) -> str:
    for threshold, name in _TEMPERATURE_THRESHOLDS:
        if modified_roll <= threshold:
            return name
    return "Boiling"
```

**Risk:** Low — functionally equivalent; add a test assertion before removing
the original.

---

## Issue 6 — Import shared `_interp` instead of duplicating it

**Files:** `traveller_stellar_gen.py`, `traveller_orbit_gen.py`

Both modules implement the same linear interpolation over
`(spectral_type, subtype_anchor, lum_class)` table keys with the same fallback
logic. `traveller_orbit_gen.py` already imports from `traveller_stellar_gen.py`
(for `Star`, `ORBIT_AU`), so `_interp` could be imported from there rather than
redefined.

**Risk:** Low — remove duplication; if the two copies ever diverged silently this
would surface as a test failure rather than a hidden discrepancy.

---

## Priority summary

| # | Title | Risk |
|---|-------|------|
| 1 | NamedTuple for anonymous table tuples | Low |
| 6 | Import shared `_interp` | Low |
| 3 | Modernise typing imports | None |
| 2 | Align `roll()` signatures | None |
| 5 | Table-driven dispatch functions | Low |
| 4 | Remove `global _rng` side-effect | Medium |
