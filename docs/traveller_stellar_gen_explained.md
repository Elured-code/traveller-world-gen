# Understanding `traveller_stellar_gen.py`

A guide for Python beginners. This file generates the star system that a Traveller
world orbits — how many stars there are, what type they are, how old, and how bright.

---

## What this file does

Every Traveller system starts with its star or stars. This file generates:

- **Spectral type and luminosity class** — is the primary a Sun-like G-class main
  sequence star, a hot blue O giant, a cool red M dwarf, a white dwarf, a neutron
  star, a black hole, or a pulsar?
- **Physical properties** — mass, temperature, diameter, and luminosity (derived
  via the Stefan-Boltzmann formula); Schwarzschild diameter for black holes
- **System age** — how many billion years old the system is; affects whether
  the primary has evolved off the main sequence
- **Companion stars** — close, near, and far companions; each may have its own
  companions (e.g. a "Ca" star orbits "C")

The file covers WBH pp.14–29 and the unusual/peculiar star tables from WBH p.219.

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
    spectral_type: str    # "G", "M", "K", "D" (white dwarf), "BD" (brown dwarf),
                          # "NS" (neutron star), "PSR" (pulsar), "BH" (black hole)
    subtype: Optional[int]  # None for D, BD, NS, PSR, BH
    lum_class: str        # "V" (main sequence), "III" (giant), "D", "BD",
                          # "NS", "PSR", "BH"
    mass: float           # Solar masses
    temperature: int      # Kelvin; 0 for black holes
    diameter: float       # Solar diameters
    luminosity: float     # Solar luminosities; 0.0 for black holes
    orbit_number: float   # Orbit# of this star around primary (0.0 for primary)
    orbit_au: float
    age_gyr: float
    ms_lifespan_gyr: float
    # Post-init field:
    bh_schwarzschild_km: Optional[float]  # field(default=None); set for BH stars only
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
system = generate_stellar_data(rng=None, unusual_stars=False)
```

This runs the full WBH pp.14–29 procedure in order. The optional `rng` parameter
accepts a `random.Random` instance; when supplied it is used for all dice rolls in
this module instead of the module-level default. `generate_full_system()` always
passes its shared `rng` here so the entire system uses one reproducible sequence.

When `unusual_stars=True`, the Unusual column (WBH p.219) is used instead of the
Special column when the primary type roll comes up ≤ 2. This can produce neutron
stars, black holes, pulsars, and environment types (nebulae, protostars, etc.).

1. Roll primary spectral type and luminosity class
2. If unusual_stars=True and roll ≤ 2: Unusual column → possibly Peculiar sub-roll
3. Look up or interpolate physical properties (mass, temperature, diameter)
4. For WD/NS/PSR/BH: roll dice-based physical properties instead of table lookup
5. Compute luminosity via Stefan-Boltzmann (zero for BH)
6. Determine system age
7. Check for companion stars (close, near, far)
8. For each companion: determine type and roll properties

Returns a `StarSystem` with all stars populated.

---

## Post-stellar remnant characterization (WBH p.219)

When `unusual_stars=True` and the Peculiar sub-roll produces a dead star result,
dedicated helper functions replace the standard table lookups:

**White Dwarf (`_characterize_white_dwarf(age_gyr)`):**
- Mass: `(2D − 1) / 10 + d10 / 100` ☉ (range 0.11–1.20, capped at 1.44)
- Diameter: `0.01 / mass` solar diameters
- Temperature: interpolated from `_WD_AGING_TABLE` (breakpoints at 0–13 Gyr for 0.6 ☉),
  then scaled by `mass / 0.6`
- Luminosity: Stefan-Boltzmann using radius = diameter / 2

**Neutron Star (`_characterize_neutron_star(age_gyr)`):**
- Mass: 1D/10 bonus; if roll = 6, add another (1D − 1)/10 (range 1.1–2.1 ☉)
- Diameter: `19 + 1D` km ÷ 695700 (solar diameters)
- Temperature: same WD Aging interpolation scaled by mass/0.6 (approximation)
- Luminosity: Stefan-Boltzmann

**Black Hole (`_characterize_black_hole()`):**
- Mass: `2.1 + exploding_1D − 1 + d10/10` ☉ (exploding: keep adding if 6 rolled)
- Schwarzschild diameter: `5.9 × mass` km ÷ 695700
- Temperature: 0; Luminosity: 0.0
- `bh_schwarzschild_km` field set to `5.9 × mass`

**Pulsar (PSR):** same dice as neutron star; `spectral_type = "PSR"`, `lum_class = "PSR"`

Environment types (Nebula, Protostar, Star Cluster, Anomaly) fall back to a Giants-class
star with `special_notes` describing the environment — WBH implies no dedicated host star.

---

## Key methods

| Method | On class | What it does |
|--------|----------|-------------|
| `.to_dict()` | `Star` | Serialises one star to a plain dict (includes `bh_schwarzschild_km` when set) |
| `.to_dict()` | `StarSystem` | Serialises all stars + metadata |
| `.summary()` | `StarSystem` | Human-readable multi-line description |
| `.from_dict(d)` | `Star` | Class method — reconstructs a `Star` from a dict |
| `.from_dict(d)` | `StarSystem` | Class method — reconstructs a `StarSystem` from a dict |
| `generate_stellar_data(rng, unusual_stars)` | module | Entry point; `unusual_stars=True` enables the WBH p.219 Unusual column |
| `generate_primary_star(designation, unusual_stars)` | module | Generates the primary star, routing through Unusual/Peculiar columns if flag set |
| `_wd_temperature(age_gyr, mass)` | module | Interpolates WD temperature from aging table, scaled by mass/0.6 |
| `_characterize_white_dwarf(age_gyr)` | module | Rolls WD physical properties (mass, temp, diam, lum) |
| `_characterize_neutron_star(age_gyr)` | module | Rolls NS physical properties |
| `_characterize_black_hole()` | module | Rolls BH mass and Schwarzschild diameter |
| `_generate_peculiar_star(designation, spectral, lum_class)` | module | Dispatcher for Peculiar column results |

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
