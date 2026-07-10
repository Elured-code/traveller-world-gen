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
    slot_index: int         # sequential position in this star's orbit list —
                             # continuous across a star's inner+outer placement
                             # zones (Session 167 fix; see note below)
    world_type: str         # "gas_giant" | "terrestrial" | "belt" | "empty"
    is_habitable_zone: bool # True when |hz_deviation| ≤ 1.0
    hz_deviation: float     # orbit_number − HZCO; negative = warmer
    temperature_zone: str   # "boiling" | "hot" | "temperate" | "cold" | "frozen"
    is_mainworld_candidate: bool
    canonical_profile: str  # TravellerMap systems: overrides generated UWP
    gg_sah: str             # gas giant SAH, e.g. "GM9" — empty for non-GGs
    gg_mass_earth: Optional[float]  # GG mass in Earth masses (None for non-GGs)
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

**Inner/outer placement zones:** when a star has a companion close enough to
carve out an exclusion band around it (see "Primary star outer zone" in
`context/stellar-orbit.md`), that star's own worlds get placed in **two
separate passes** — an inner zone and an outer zone, each with its own
`baseline`/`spread`/`slots` calculation — instead of one continuous pass.

**Bug fixed (Session 167):** `slot_index` was being assigned from each zone's
own local `enumerate(slots)` (`si + 1`), so it reset to 1 for the outer
zone instead of continuing from the inner zone's last value — e.g. a star
with 3 inner-zone slots and 4 outer-zone slots would number them 1,2,3,1,2,3,4
instead of 1–7. This wasn't just cosmetic:
`traveller_world_detail.py`'s `attach_detail()` keys its per-orbit
`WorldDetail` results by `f"{star_designation}-{slot_index}"`, so two
*different* orbit slots on the same star could collide on the same key,
silently overwriting one's generated detail with the other's. Fixed with a
single `slot_counter` declared once per star, before the zones loop, and
incremented (not reset) across both zones.

---

## Gas giant mass: `_roll_gg_mass()`

Every gas giant orbit slot has a `gg_mass_earth` value (in Earth masses) rolled from
the WBH mass table:

| GG category | Formula | Range |
|---|---|---|
| GS (small) | 5 × (1D + 1) | 10–35 M⊕ |
| GM (medium) | 20 × (3D − 1) | 40–340 M⊕ |
| GL (large) | D3 × 50 × (3D + 4) | 350–3,300 M⊕ |

The result is stored as `OrbitSlot.gg_mass_earth` and round-tripped through
`to_dict()` / `from_dict()`. Non-GG slots have `gg_mass_earth = None`.

This mass is used by `generate_moons()` to check whether a moon's perigee lies
inside the Roche limit (see `traveller_moon_gen_explained.md`).

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `OrbitSlot` | Serialises the slot to a plain dict |
| `.to_dict()` | `SystemOrbits` | Serialises all slots and zone data |
| `.from_dict(d)` | `OrbitSlot` | Reconstructs from a dict (detail sub-key optional) |
| `.from_dict(d, star_system)` | `SystemOrbits` | Reconstructs from a dict |
| `generate_orbits(star_system, ...)` | module | Entry point; accepts optional `rng` |
| `roll_eccentricity(rng=None)` | module | Rolls one eccentricity value; accepts optional `rng` |
| `roll_inclination(rng=None)` | module | Rolls one inclination value; accepts optional `rng` |

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
