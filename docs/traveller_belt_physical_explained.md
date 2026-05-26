# Understanding `traveller_belt_physical.py`

A guide for Python beginners. This file generates physical detail for asteroid belt
worlds — their span, composition, bulk, resource rating, and significant body counts.

---

## What this file does

When a world's UWP Size code is 0 (an asteroid belt), the physical detail is
completely different from a terrestrial world. Instead of diameter and gravity,
a belt has:

- **Span** — how wide the belt is in AU
- **Composition** — percentage split between metallic (iron), silicate (rocky),
  carbonaceous (carbon-rich), and other material
- **Bulk** — an abstract measure of total material (affected by system age and
  composition)
- **Resource rating** — how economically valuable the belt is
- **Significant bodies** — count of large objects (Size 1, ~1,600 km) and
  small ones (Size S, ~600 km)

Implements WBH pp.131–133.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `random`, `dataclass` |
| Composition tables | `_COMP_RESULT` — roll result → (m%, s%, c%) formulae |
| `BeltPhysical` dataclass | All belt physical fields |
| Internal helpers | `_belt_composition()`, `_belt_bulk()`, etc. |
| `generate_belt_physical()` | Entry point |

---

## Key Python concept: percentage composition and normalisation

Belt composition is expressed as percentages of three material types. The WBH gives
formulae for each type based on a 2D roll:

```python
m_type = max(0, 15 * roll_result - 15)   # metallic %
s_type = max(0, ...)                       # silicate %
c_type = max(0, ...)                       # carbonaceous %
```

The three percentages may not add up to exactly 100 %. The code normalises them:
if `m + s + c > 100`, it trims the excess from metallic first, then from silicate:

```python
if total > 100:
    excess = total - 100
    trim_m = min(m_type, excess)
    m_type -= trim_m
    excess -= trim_m
    s_type -= min(s_type, excess)
```

The remainder (`100 − m − s − c`) is labelled "other".

---

## Key Python concept: the `BeltPhysical` dataclass

```python
@dataclass
class BeltPhysical:
    inner_au: float        # inner edge of the belt span
    outer_au: float        # outer edge of the belt span
    m_type_pct: int        # metallic percentage
    s_type_pct: int        # silicate percentage
    c_type_pct: int        # carbonaceous percentage
    other_pct: int         # residual "other" percentage
    bulk: int              # belt bulk (WBH p.132)
    resource_rating: int   # economic rating 2–12
    size_1_bodies: int     # count of Size 1 objects
    size_s_bodies: int     # count of Size S objects
    mean_temperature_k: int  # temperature from orbital HZ position
```

This is a `@dataclass` without any `init=False` fields — all values are known at
construction time. `BeltPhysical` is either attached to `World.size_detail` (for
belt mainworlds) or to `WorldDetail.physical` (for belt orbit slots).

---

## Resource rating and Industrial DM

The resource rating is affected by who is mining the belt. If the **mainworld** has
the Industrial trade code (`In`) and tech level ≥ 8, the belt's resource rating is
reduced by 1D — representing exploitation that has already extracted the easiest ore:

```python
if is_industrial and mainworld_tl >= 8:
    resource_rating -= roll(1)
resource_rating = max(2, min(12, resource_rating))
```

The `max(2, min(12, ...))` clamp ensures the result stays in the valid range.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `BeltPhysical` | Serialises all fields to a plain dict |
| `.from_dict(d)` | `BeltPhysical` | Class method — reconstructs from a dict |
| `generate_belt_physical(orbit_slot, ...)` | module | Entry point |

---

## How this fits in the pipeline

```
attach_detail()
        │
        ├─ for belt orbit slots:
        │       generate_belt_physical(slot, ...)  →  BeltPhysical
        │       WorldDetail.physical = BeltPhysical
        │
        └─ for belt mainworld:
                generate_belt_physical(mw_orbit, ...)  →  BeltPhysical
                World.size_detail = BeltPhysical
```

`BeltPhysical` takes the place of `WorldPhysical` for Size 0 worlds. Both are stored
in the same `physical` / `size_detail` attribute, which is typed as
`BeltPhysical | WorldPhysical | None`.
