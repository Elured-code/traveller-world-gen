# Understanding `traveller_stellar_gen.py`

A guide for Python beginners. This file generates the star system that a Traveller
world orbits — how many stars there are, what type they are, how old, and how bright.

---

## What this file does

Every Traveller system starts with its star or stars. This file generates:

- **Spectral type and luminosity class** — is the primary a Sun-like G-class main
  sequence star, a hot blue O giant, a cool red M dwarf, a white dwarf?
- **Physical properties** — mass, temperature, diameter, and luminosity (derived
  via the Stefan-Boltzmann formula)
- **System age** — how many billion years old the system is; affects whether
  the primary has evolved off the main sequence
- **Companion stars** — close, near, and far companions; each may have its own
  companions (e.g. a "Ca" star orbits "C")

The file covers WBH pp.14–29.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | Standard library + math |
| Dice helpers | `roll()`, `d3()`, `d10()` |
| Look-up tables | `ORBIT_AU`, spectral-type tables, mass/temperature tables |
| `Star` dataclass | One star's physical data |
| `StarSystem` dataclass | The full set of stars in the system |
| Generator functions | One per step of the WBH procedure |
| `generate_stellar_data()` | Entry point |

---

## Key Python concept: interpolation

Star properties (mass, temperature, diameter) are given in the WBH tables only for
subtypes 0 and 5. For subtypes 1–4 and 6–9 the code **interpolates** between the
two nearest table entries:

```python
def _interp(subtype, v0, v5, v10=None):
    if subtype <= 5:
        return v0 + (v5 - v0) * (subtype / 5)
    ...
```

This is a straight-line (linear) interpolation: at subtype 0 you get `v0`, at
subtype 5 you get `v5`, and at subtype 3 you get the value 60 % of the way between
them.

---

## Key Python concept: nested dataclasses

```python
@dataclass
class Star:
    designation: str      # "A", "Aa", "B", "Ca", ...
    role: str             # "primary" | "companion" | "close" | "near" | "far"
    spectral_type: str    # "G", "M", "K", "D" (white dwarf), "BD" (brown dwarf)
    subtype: Optional[int]
    lum_class: str        # "V" (main sequence), "III" (giant), "D", "BD", ...
    mass: float           # Solar masses
    temperature: int      # Kelvin
    diameter: float       # Solar diameters
    luminosity: float     # Solar luminosities
    orbit_number: float   # Orbit# of this star around primary (0.0 for primary)
    orbit_au: float
    age_gyr: float
    ms_lifespan_gyr: float
    ...

@dataclass
class StarSystem:
    stars: List[Star]     # Index 0 is always the primary
```

`StarSystem` wraps a list of `Star` objects. The primary is always `stars[0]`.
Companion stars have the same `orbit_number` as their parent but a different
`designation` (parent `"A"` → companions `"Aa"`, `"Ab"`).

---

## Key Python concept: the Stefan-Boltzmann formula

Luminosity is not rolled — it is *calculated* from temperature and diameter:

```python
luminosity = (diameter ** 2) * ((temperature / T_SUN) ** 4)
```

- `T_SUN` is the Sun's surface temperature (5778 K).
- Dividing by `T_SUN` normalises the temperature ratio to 1.0 for a Sun-like star.
- Squaring `diameter` and raising the temperature ratio to the fourth power gives
  luminosity in Solar luminosities.

This is physics, not a dice roll — the WBH uses this formula directly.

---

## The entry point

```python
system = generate_stellar_data(rng=None)
```

This runs the full WBH pp.14–29 procedure in order. The optional `rng` parameter
accepts a `random.Random` instance; when supplied it is used for all dice rolls in
this module instead of the module-level default. `generate_full_system()` always
passes its shared `rng` here so the entire system uses one reproducible sequence.

1. Roll primary spectral type and luminosity class
2. Look up or interpolate physical properties (mass, temperature, diameter)
3. Compute luminosity via Stefan-Boltzmann
4. Determine system age
5. Check for companion stars (close, near, far)
6. For each companion: determine type (random / lesser / sibling / twin) and roll properties

Returns a `StarSystem` with all stars populated.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `Star` | Serialises one star to a plain dict |
| `.to_dict()` | `StarSystem` | Serialises all stars + metadata |
| `.summary()` | `StarSystem` | Human-readable multi-line description |
| `.from_dict(d)` | `Star` | Class method — reconstructs a `Star` from a dict |
| `.from_dict(d)` | `StarSystem` | Class method — reconstructs a `StarSystem` from a dict |

---

## How this fits in the pipeline

`generate_stellar_data()` is the first step in `generate_full_system()` (see
`traveller_system_gen.py`). The `StarSystem` it returns drives orbit generation:
the primary star's luminosity determines the Habitable Zone Centre Orbit#, and each
star's spectral type and mass affect which orbit slots are viable.

```
generate_stellar_data()   →  StarSystem
        │
        ▼
generate_orbits(star_system)  →  SystemOrbits
```
