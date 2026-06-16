# Understanding `world_codes.py`

A guide for Python beginners. This file defines the shared type-safe code enumerations
and the application version constant used across the whole project.

---

## What this file does

Traveller world codes are strings and integers, but raw strings and integers are
easy to misspell or confuse. `world_codes.py` wraps the most-used code sets in
Python **enumerations** — named constants with built-in validation.

The file also holds `APP_VERSION`, the single source of truth for the version string
that appears in saved JSON files.

---

## Key Python concept: `StrEnum`

A `StrEnum` is an enumeration where each member is also a string. This gives you
the safety of named constants while allowing the values to be used anywhere a plain
string is expected:

```python
from enum import StrEnum

class StarportCode(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    X = "X"
```

Using `StarportCode.A` in code is safer than the bare string `"A"` — a typo like
`StarportCode.Aa` raises an `AttributeError` immediately, while `"Aa"` would silently
produce wrong output.

```python
starport = StarportCode.A     # type: StarportCode, value: "A"
print(starport == "A")        # True — StrEnum members compare equal to their string value
print(f"Starport: {starport}")  # "Starport: A" — works in f-strings
```

---

## Key Python concept: `IntEnum`

`IntEnum` is the integer equivalent. Each member is both a named constant and an
integer:

```python
class AtmosphereCode(IntEnum):
    NONE              = 0
    TRACE             = 1
    VERY_THIN_TAINTED = 2
    ...
    CORROSIVE         = 11
    INSIDIOUS         = 12
    ...
    GAS_GIANT_H       = 16
    GAS_GIANT_I       = 17
```

`AtmosphereCode.CORROSIVE == 11` is `True`. This lets code use the named constant
for readability while still working with numeric lookup tables that use integer keys.

---

## What is defined here

| Name | Type | Purpose |
|------|------|---------|
| `StarportCode` | `StrEnum` | UWP starport quality codes A–X |
| `TemperatureCategory` | `StrEnum` | Frozen / Cold / Temperate / Hot / Boiling |
| `TradeCode` | `StrEnum` | All standard Traveller trade classification codes |
| `TravelZone` | `StrEnum` | Green / Amber / Red |
| `AtmosphereCode` | `IntEnum` | All atmosphere codes 0–17 including NHZ codes 16 (G) and 17 (H) |
| `APP_VERSION` | `str` | `"1.5.1"` — used when saving JSON files |
| `gg_diameter_from_sah` | `function` | Decode the eHex diameter digit from a gas-giant SAH string (e.g. `"GM9"` → 9) |

---

## `APP_VERSION`

```python
APP_VERSION = "1.5.1"
```

When a world or system is saved to JSON, the file includes:

```json
{ "_app_version": "1.5.0", ... }
```

When a JSON is loaded, the GUI checks the saved version against `APP_VERSION` and
warns the user if they differ. `APP_VERSION` living in `world_codes.py` means it is
imported by both the generation code (`traveller_world_gen.py`) and the GUI
(`gen-ui/app.py`) from the same place — there is only one version string to update
when a new release is made.

---

## `gg_diameter_from_sah` — shared gas giant utility (Session 116)

Gas giant SAH strings encode the giant's diameter in the third character using
eHex notation (the same base-20 scale used by UWP digits). For example, `"GM9"`
means category M, diameter 9 Terran diameters; `"GLA"` means category L, diameter
10.

Both `traveller_system_gen.py` (satellite size cap) and `traveller_world_detail.py`
(moon generation) need to decode this digit. Rather than keeping a private copy
in each module, Session 116 moved the function to `world_codes.py`:

```python
def gg_diameter_from_sah(gg_sah: str) -> int:
    if len(gg_sah) >= 3:
        idx = _EHEX.find(gg_sah[2].upper())
        if idx >= 0:
            return idx
    return 8   # safe default (medium GG)
```

Both modules now import it with `from world_codes import gg_diameter_from_sah`.

---

## How this fits in the pipeline

`world_codes.py` has no imports of its own. It is imported by every module that
needs the code enumerations or the version string:

```
world_codes.py  (no imports)
    ↑
    │ imported by
    ├── traveller_world_gen.py    (AtmosphereCode, StarportCode, APP_VERSION, ...)
    ├── traveller_system_gen.py   (APP_VERSION, gg_diameter_from_sah)
    ├── traveller_world_detail.py (gg_diameter_from_sah)
    ├── gen-ui/app.py             (APP_VERSION)
    └── (any other module needing type-safe code constants)
```
