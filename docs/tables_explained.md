# Understanding `tables.py`

A guide for Python beginners. This file is the single source of truth for all
display-layer lookup tables used across the project.

---

## What this file does

Traveller has hundreds of codes, and almost every code needs a human-readable label
for display. Rather than defining the same label in the world generator, the HTML
templates, the GUI, and the API separately, all label data lives in `tables.py`.

The file exports pure lookup dictionaries. No functions, no classes, no side effects —
just data.

---

## What is stored here

| Constant | Maps | Example |
|----------|------|---------|
| `SIZE_DIAMETER_LABEL` | Size code → diameter string | `8 → "12,800"` |
| `SIZE_GRAVITY_LABEL` | Size code → gravity string | `8 → "1.00G"` |
| `POPULATION_RANGE` | Population code → range description | `9 → "Billions"` |
| `TRADE_CODE_FULL` | Trade code → full label | `"Ag" → "Ag — Agricultural"` |
| `BASE_FULL` | Base code → full name | `"N" → "Naval Base"` |
| `ZONE_CSS_CLASS` | Travel zone → CSS class | `"Amber" → "amber-zone"` |
| `TIDAL_STATUS_LABELS` | Tidal lock status string → display label | `"1:1_lock" → "Tidally locked"` |
| `BIOCOMPLEXITY_DESC` | Biocomplexity value → description | `0 → "Microbial only"` |

---

## Key Python concept: why one file?

Without `tables.py`, each label might be defined in multiple places and could
drift out of sync. For example, the gravity label for Size 8 might be `"1.00G"` in
the world generator but `"1.0G"` in the HTML template. By importing from one shared
file, all callers see the same label:

```python
# In traveller_world_gen.py:
from tables import SIZE_GRAVITY_LABEL
gravity_label = SIZE_GRAVITY_LABEL.get(world.size, "unknown")

# In gen-ui/app.py:
from tables import SIZE_GRAVITY_LABEL
gravity_label = SIZE_GRAVITY_LABEL[world.size]
```

Both callers reference the same dict, so the label is always consistent.

---

## Key Python concept: what is NOT stored here

Physics constants (e.g. Earth's diameter in km, the Stefan-Boltzmann constant) live
next to the code that uses them, not in `tables.py`. The rule is: if a value is used
in a *calculation*, it stays with the calculation. If a value is only used for
*display*, it belongs in `tables.py`.

---

## Adding to tables.py

If a new code or label is needed anywhere in the project:

1. Add the entry to the appropriate dict in `tables.py`
2. Import the dict in every module that needs it

Do **not** define the same label in two places. The dict in `tables.py` is the
single authoritative source.

---

## How this fits in the pipeline

`tables.py` is imported by nearly every other module. It has no imports of its
own — it is a pure data file. This means it can be safely imported anywhere
without risk of circular imports.

```
tables.py  (no imports)
    ↑
    │ imported by
    ├── traveller_world_gen.py
    ├── traveller_system_gen.py
    ├── traveller_world_detail.py
    ├── gen-ui/app.py
    └── (all other display/generation modules)
```
