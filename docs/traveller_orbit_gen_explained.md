# Understanding `traveller_orbit_gen.py`

A guide for Python beginners. This file decides how many worlds are in a star system,
where each one orbits, and which slot becomes the mainworld candidate.

---

## What this file does

Once the stars are known (from `traveller_stellar_gen.py`), this file:

- Rolls world **counts** — how many gas giants, asteroid belts, and terrestrial worlds
- Computes the **Habitable Zone** centre orbit and boundaries
- Places every world in an **orbit slot** using the WBH stepped placement procedure
- Assigns **anomalous orbits** (eccentric, inclined, retrograde, trojan)
- Selects the **mainworld candidate** — the slot used as the UWP mainworld

Implements WBH pp.36–51.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| MAO tables | Minimum Allowable Orbit# by star class/subtype |
| Orbit-to-AU conversion | `ORBIT_AU` dict; `_orbit_to_au()` helper |
| `OrbitSlot` dataclass | One orbit slot's data |
| `SystemOrbits` dataclass | The full set of slots for all stars |
| Generator functions | Steps 1–7 from the WBH procedure |
| `generate_orbits()` | Entry point |

---

## Key Python concept: the `OrbitSlot` dataclass

Each occupied orbit in the system is represented as an `OrbitSlot`:

```python
@dataclass
class OrbitSlot:
    star_designation: str   # which star this orbits ("A", "B", ...)
    orbit_number: float     # WBH Orbit# (non-linear scale; see table below)
    orbit_au: float         # distance from the star in AU
    slot_index: int         # sequential position in this star's orbit list
    world_type: str         # "gas_giant" | "terrestrial" | "belt" | "empty"
    is_habitable_zone: bool # True when |hz_deviation| ≤ 1.0
    hz_deviation: float     # orbit_number − HZCO; negative = warmer
    temperature_zone: str   # "boiling" | "hot" | "temperate" | "cold" | "frozen"
    is_mainworld_candidate: bool
    canonical_profile: str  # TravellerMap systems: overrides generated UWP
    gg_sah: str             # gas giant SAH, e.g. "GM9" — empty for non-GGs
    anomaly_type: str       # "" | "random" | "eccentric" | "inclined" | ...
    notes: str
    # Post-init fields (set after construction):
    orbit_period_yr: Optional[float]
    eccentricity: float
    inclination: float
    detail: Optional[WorldDetail]  # set by attach_detail()
```

---

## Key Python concept: non-linear scales (the Orbit# system)

WBH Orbit numbers are **not** the same as AU distances. They are a stepped index
table where small orbit numbers correspond to the inner solar system and large numbers
to the outer. The file stores the conversion in a dict:

```python
ORBIT_AU: dict[float, float] = {
    0.0: 0.2, 0.5: 0.35, 1.0: 0.5, 2.0: 0.9, 3.0: 1.4, 4.0: 2.0, ...
}
```

Converting Orbit# to AU uses linear interpolation between the two nearest table
entries:

```python
def _orbit_to_au(orbit_number: float) -> float:
    ...   # interpolate in ORBIT_AU
```

This is the same interpolation pattern used in `traveller_stellar_gen.py`.

---

## Key Python concept: the Habitable Zone

The **Habitable Zone Centre Orbit#** (HZCO) is derived purely from the star's
luminosity — no dice roll:

```python
hzco = round(math.sqrt(luminosity), 2)
```

(Approximately — the WBH gives it as `√L` in Orbit# units.) The habitable zone
extends ±1.0 Orbit# from the HZCO.

`hz_deviation = orbit_number − HZCO`. Negative values mean the orbit is closer
to the star (warmer); positive values mean it is further out (cooler). The
temperature zone (`"boiling"`, `"hot"`, `"temperate"`, `"cold"`, `"frozen"`) is
derived from the magnitude of the deviation.

---

## Key Python concept: `SystemOrbits`

```python
@dataclass
class SystemOrbits:
    stellar_system: StarSystem
    gas_giant_count: int
    belt_count: int
    terrestrial_count: int
    total_worlds: int
    empty_orbits: int
    orbits: List[OrbitSlot]        # all slots for all stars
    mainworld_orbit: Optional[OrbitSlot]
    star_mao: dict[str, float]     # min allowable orbit# per star designation
    star_hzco: dict[str, float]    # HZCO per star designation
    star_hz_inner: dict[str, float]
    star_hz_outer: dict[str, float]
```

`SystemOrbits` holds every orbit slot across every star in the system, plus the
zone boundaries for each star. The `mainworld_orbit` field points to the slot that
was chosen as the mainworld.

---

## How world placement works

1. **Counts** — roll gas giants, belts, terrestrials (WBH p.36–37)
2. **Baseline** — determine how many orbits to skip from MAO (Steps 3a/3b/3c)
3. **Empty orbits** — some slots are left empty (Step 4)
4. **Spread** — divide the orbit range into equal steps (Step 5)
5. **Slot placement** — fill slots in order: empties, gas giants, belts, terrestrials (Step 6)
6. **Mainworld** — pick the best inhabited or HZ candidate (p.51)
7. **Anomalies** — randomly assign eccentric/inclined/retrograde/trojan orbits (Step 7)

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `OrbitSlot` | Serialises the slot to a plain dict |
| `.to_dict()` | `SystemOrbits` | Serialises all slots and zone data |
| `.from_dict(d)` | `OrbitSlot` | Reconstructs from a dict (detail sub-key optional) |
| `.from_dict(d, star_system)` | `SystemOrbits` | Reconstructs from a dict |
| `generate_orbits(star_system, ...)` | module | Entry point |

---

## How this fits in the pipeline

```
generate_stellar_data()   →  StarSystem
        │
        ▼
generate_orbits(star_system)  →  SystemOrbits
        │                         (OrbitSlot × N)
        ▼
generate_full_system()    →  TravellerSystem
```

Each `OrbitSlot` starts with `detail = None`. The `attach_detail()` call in
`traveller_world_detail.py` fills `detail` with a `WorldDetail` object for every
significant (non-empty) orbit slot.
