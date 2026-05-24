# data-structures.md — Key data structures

Read this when working with data structures, type signatures, dataclasses,
HZ/temperature logic, or the Orbit# coordinate system.

---

## `Star` (`traveller_stellar_gen.py`)

```python
@dataclass
class Star:
    designation: str        # "A", "Aa", "Ab", "B", "Ca"
    role: str               # "primary"|"companion"|"close"|"near"|"far"
    spectral_type: str      # "O"|"B"|"A"|"F"|"G"|"K"|"M"|"D"|"BD"
    subtype: Optional[int]  # 0-9; None for white dwarfs (D) and brown dwarfs (BD)
    lum_class: str          # "Ia"|"Ib"|"II"|"III"|"IV"|"V"|"VI"|"D"|"BD"
    mass: float             # Solar masses
    temperature: int        # Kelvin
    diameter: float         # Solar diameters
    luminosity: float       # Solar luminosities (Stefan-Boltzmann derived)
    orbit_number: float     # Orbit# of this star around the primary (0.0 for primary)
    orbit_au: float
    age_gyr: float          # System age in Gyr (same for all stars in the system)
    ms_lifespan_gyr: float  # Main sequence lifespan in Gyr
    orbit_period_yr: Optional[float]  # Orbital period in years; None for primary
    orbit_eccentricity: float = 0.0   # 0.0 until generate_orbits() populates it
    orbit_inclination: float = 0.0    # 0.0 until generate_orbits() populates it

@dataclass
class StarSystem:
    stars: List[Star]       # Index 0 is always the primary
    # properties: .primary (→ stars[0]), .age_gyr (→ stars[0].age_gyr)
```

**Companion stars** share the same `orbit_number` as their parent and have
`role="companion"`. Their designation is the parent's + a lowercase letter
(parent `"A"` → companions `"Aa"`, `"Ab"`).

---

## `OrbitSlot` (`traveller_orbit_gen.py`)

```python
@dataclass
class OrbitSlot:
    star_designation: str
    orbit_number: float         # WBH Orbit# — non-linear with AU (see table below)
    orbit_au: float
    slot_index: int
    world_type: str             # "gas_giant"|"terrestrial"|"belt"|"empty"
    is_habitable_zone: bool     # True if |hz_deviation| <= 1.0
    hz_deviation: float         # orbit_number - HZCO; negative = warmer, positive = cooler
    temperature_zone: str       # "boiling"|"hot"|"temperate"|"cold"|"frozen"
    is_mainworld_candidate: bool
    canonical_profile: str      # TravellerMap systems: canonical UWP for mainworld slot;
                                # takes display priority over detail.profile
    gg_sah: str                 # Gas giant SAH rolled at orbit-gen time (e.g. "GM9");
                                # empty string for non-gas-giant slots
    anomaly_type: str           # ""|"random"|"eccentric"|"inclined"|"retrograde"
                                # |"trojan_leading"|"trojan_trailing"; "" for normal orbits
    orbit_period_yr: Optional[float]  # field(default=None, init=False); orbital period
                                      # in years; None for empty slots
    eccentricity: float         # field(default=0.0, init=False); 0.0 when
                                # orbital_eccentricity=False (default)
    inclination: float          # field(default=0.0, init=False); 0.0 when
                                # orbital_inclination=False (default);
                                # not set for anomaly_type=="inclined" slots
    notes: str
    detail: Optional[WorldDetail] = field(default=None, init=False)
                                # populated by attach_detail(); None until then
```

## `SystemOrbits` (`traveller_orbit_gen.py`)

```python
@dataclass
class SystemOrbits:
    stellar_system: StarSystem
    gas_giant_count: int
    belt_count: int
    terrestrial_count: int
    total_worlds: int
    empty_orbits: int
    orbits: List[OrbitSlot]         # sorted by (star_designation, orbit_au)
    mainworld_orbit: Optional[OrbitSlot]
    star_mao: Dict[str, float]      # Minimum Allowable Orbit# per star designation
    star_hzco: Dict[str, float]     # HZCO per star designation
    star_hz_inner: Dict[str, float] # HZCO - 1.0 (clamped to MAO)
    star_hz_outer: Dict[str, float] # HZCO + 1.0
```

---

## `TravellerSystem` (`traveller_system_gen.py`)

```python
@dataclass
class TravellerSystem:
    stellar_system: StarSystem
    system_orbits: SystemOrbits
    mainworld: Optional[World]
    mainworld_orbit: Optional[OrbitSlot]
    nhz_atmospheres: bool = False   # set by generate_full_system(); read by attach_detail()
    orbital_eccentricity: bool = False  # set by generate_full_system()
    orbital_inclination: bool = False   # set by generate_full_system()
    # methods: .to_dict(), .to_json(), .to_html(detail_attached), .summary()
```

---

## `World` (`traveller_world_gen.py`)

```python
@dataclass
class World:
    name: str
    size: int; atmosphere: int
    atmosphere_detail: Optional[AtmosphereDetail] = None  # WBH pp. 78-82
    temperature: str
    hydrographics: int; population: int; government: int
    law_level: int; starport: str; tech_level: int
    has_gas_giant: bool; gas_giant_count: int; belt_count: int
    population_multiplier: int      # WBH "P" digit (1-9; 0 if uninhabited)
    bases: List[str]                # "N"|"S"|"M"|"H"|"C"
    trade_codes: List[str]          # e.g. ["Ag","Ni","Ri"]
    travel_zone: str                # "Green"|"Amber"|"Red"
    notes: List[str]
    hydrographic_detail: Optional[HydrographicDetail] = None  # WBH p.93
    physical: Optional[Union["WorldPhysical", BeltPhysical]] = field(default=None, init=False)
                                    # set by attach_detail() for belt mainworlds (BeltPhysical),
                                    # or by generate_world_physical() for terrestrial mainworlds
    biomass_rating: Optional[int] = field(default=None, init=False)
                                    # set by _apply_biomass() at end of attach_detail();
                                    # only when WorldPhysical is set (Mainworld Detail required);
                                    # 0 = no native life; positive = life present
    biocomplexity_rating: Optional[int] = field(default=None, init=False)
                                    # set by _apply_biomass(); None when biomass 0 or not computed;
                                    # min 1 when set
    native_sophont: bool = field(default=False, init=False)
                                    # True when current sophont confirmed (WBH p.131);
                                    # only set when biocomplexity_rating >= 8
    extinct_sophont: bool = field(default=False, init=False)
                                    # True when evidence of extinct sophont (WBH p.131);
                                    # only checked when current sophont roll fails

    # methods: .uwp(), .to_dict(), .to_json(), .to_html(), .summary()
    # classmethod: .from_dict(d) — reconstruct from to_dict() output
```

**eHex encoding:** Traveller uses base-17 for UWP digits above 9 (10=A … 16=G).
`to_hex(value)` handles this throughout. Size S moons use the string `"S"` in
code but do not appear in standard UWP strings.

**JSON Schema:** `traveller_world_schema.json` validates `World.to_dict()` output.
Uses `"additionalProperties": false` and validates UWP against
`^[ABCDEX][0-9A-G]{6}-[0-9A-G]$`.

### `AtmosphereDetail` (`traveller_world_gen.py`)

```python
@dataclass
class AtmosphereDetail:
    pressure_bar:            Optional[float]  # WBH p.79, codes 1-9, D, E
    oxygen_partial_pressure: Optional[float]  # WBH p.80, codes 2-9, D, E only
    scale_height_km:         Optional[float]  # WBH p.81, 8.5/gravity approximation
    taints:                  list             # List[Taint]; non-empty for codes 2,4,7,9 and optional for 13,14
    subtype_code:            Optional[str]    # Exotic/CI subtype, e.g. "St4"
    subtype_name:            Optional[str]    # e.g. "Standard Exotic (4)"
    hazards:                 list             # List[InsidiousHazard]; code 12 (C) only
    gas_mix:                 Optional[...]    # List[GasMixComponent]; codes 10/11/12 (A/B/C) only
    min_safe_altitude_km:    Optional[float]  # Code 13: km above baseline (positive);
                                              # Code 14: km below baseline (negative)
    no_safe_altitude:        bool             # True when no breathable altitude exists
    unusual_subtypes:        list             # List[UnusualSubtype]; code 15 (F) only
    # method: .to_dict() — omits None/empty/False fields
```

Generated by `generate_atmosphere_detail(code, size, system_age_gyr=None, temperature=None, hz_deviation=None)`.
The orchestrator (`generate_mainworld_at_orbit`) calls it right after
`generate_atmosphere()` and threads `stellar.age_gyr` through so the WBH
p.80 DM+1 (system age > 4 Gyr) is applied to the oxygen-fraction roll.
`temperature` drives Phase 3/4 subtype DMs. `hz_deviation` drives orbit-position
DMs on exotic/corrosive/insidious subtype tables (WBH pp.85-87).

After hydrographics, call:
- `generate_gas_mix(detail, atm_code, size, temperature, hz_deviation, hydro)` — codes 10/11/12
- `generate_unusual_subtype(detail, atm_code, size, hydro)` — code 15 (F); post-hydro because Panthalassic/Steam need hydro

Rendered into JSON via `World._atmosphere_dict()`:
- non-None fields appear under `"atmosphere"."detail"`
- `"taints"` array when non-empty; `"hazards"`, `"gas_mix"`, `"unusual_subtypes"` similarly
- `"no_safe_altitude": true` when set; `"min_safe_altitude_km"` when not None
- a derived profile string added under `"atmosphere"."profile"` per WBH p.82

### `Taint` (`traveller_world_gen.py`)

```python
@dataclass
class Taint:
    subtype:          str   # e.g. "Radioactivity", "Particulates", "Low Oxygen"
    subtype_code:     str   # single letter: L/H/R/G/P/S
    severity_code:    int   # 1–9
    severity:         str   # e.g. "Major irritant", "Inevitably lethal: death within 1D days"
    persistence_code: int   # 2–9
    persistence:      str   # e.g. "Constant", "Fluctuating"
    # method: .to_dict() — emits subtype, severity_code, severity,
    #                       persistence_code, persistence (no subtype_code)
```

Generated by `_roll_single_taint(atm_code)`. Taint subtype DM: −2 for code
4, +2 for code 9. Biologic results (subtype table rows 4 and 9) reroll.
Result 10 on the subtype table (Particulates) triggers a cascade: a second
`_roll_single_taint` call is made and both taints are stored. L/H subtypes
apply DM+4 to severity and persistence rolls (DM+6 to persistence if
severity ≥ 8).

Tainted atmosphere codes: `_TAINTED_CODES = frozenset({2, 4, 7, 9})`.
Optional taint also rolled for codes 13 and 14 (1D≥4 inside `generate_atmosphere_detail()`).

### `UnusualSubtype` (`traveller_world_gen.py`)

```python
@dataclass
class UnusualSubtype:
    subtype_code: str   # "1"–"9", "A", "F"; "" only for the Combination sentinel (internal)
    subtype_name: str   # e.g. "Panthalassic", "Layered"
    description:  str
    # method: .to_dict() — emits subtype_code, subtype_name, description
```

Generated by `generate_unusual_subtype(detail, atm_code, size, hydro)` for code 15 (F).
D26 roll from `_UNUSUAL_SUBTYPE_TABLE`. Prerequisites: Layered (result 16) requires
size ≥ 9 (gravity > 1.2 G); Panthalassic (21) requires hydro == 10; Steam (22) requires
hydro ≥ 5. Combination result (25) produces two non-Combination subtypes.

### `HydrographicDetail` (`traveller_hydro_detail.py`)

```python
@dataclass
class HydrographicDetail:
    surface_liquid_pct: int   # 0–100; precise coverage to nearest 1% (WBH p.93)
    # method: .to_dict() — {"surface_liquid_pct": int}
```

Generated by `generate_hydrographic_detail(hydrographics, size)`.
Returns `None` for size 0 (belts) or invalid hydro codes. For hydro code 10 with
size > 9, always returns 100 (ocean world). Otherwise draws uniformly from the
WBH p.93 range for that code.

`_HYDRO_PCT_RANGE` (exported): `{code: (low, high)}` for codes 0–10.

JSON output: `hydrographics.detail.surface_liquid_pct` (nested under `"detail"` key,
matching the `atmosphere.detail.*` pattern). Absent when `hydrographic_detail is None`.

---

## `WorldPhysical` (`traveller_world_physical.py`)

```python
@dataclass
class WorldPhysical:    # pylint: disable=too-many-instance-attributes
    composition: str        # Terrestrial Composition Table category
    diameter_km: int        # actual rolled diameter in km
    density: float          # g/cm³
    mass: float             # relative to Earth (D*³ × ρ*)
    gravity: float          # surface gravity in G (D* × ρ*)
    escape_velocity: float  # km/s  (11.186 × √(gravity × D*))
    axial_tilt: float       # degrees, 0.0–180.0 (>90° = retrograde); post-tidal final value
    day_length: float       # rotation period in hours; post-tidal final value
    tidal_status: str       # "none"|"braking"|"prograde"|"retrograde"|"3:2_lock"|"1:1_lock"
    eccentricity_adjusted: Optional[float] = field(default=None, init=False)
    # Set when tidal_status=="1:1_lock" and orbit_eccentricity > 0.1 (WBH p.77 Rule 4).
    # Value = min(original_eccentricity, re-rolled eccentricity with DM-2).
    # _attach_mainworld_physical() propagates this back to the orbit slot.
    mean_temperature_k: Optional[int] = field(default=None, init=False)
    # Basic Mean Temperature in Kelvin (WBH p.47). Set when hz_deviation is passed
    # to generate_world_physical(). Computed from orbital DM + atmosphere DM applied
    # to base roll 7; extrapolates below 0 (-5K/step) and above 12 (+50K/step); min 3K.
    residual_seismic_stress: Optional[int] = field(default=None, init=False)
    tidal_seismic_stress: Optional[int] = field(default=None, init=False)
    tidal_stress_factor: Optional[int] = field(default=None, init=False)
    total_seismic_stress: Optional[int] = field(default=None, init=False)
    seismic_temperature_k: Optional[int] = field(default=None, init=False)
    tidal_amplitude_m: Optional[float] = field(default=None, init=False)
    # Seismic and tidal fields set by apply_moon_tidal_effects() (Sessions 56–60).
    # residual_seismic_stress: floor(Size - Age_Gyr + DMs)² — DMs: is_moon +1;
    #   density > 1.0 +2; density < 0.5 -1; sum of Size 1+ moon sizes capped at +12.
    # tidal_seismic_stress: PrimaryMass⊕² × (diam/1600)⁵ × e² /
    #   (3000 × dist_Mkm⁵ × period_days × WorldMass⊕); 0 when < 1; omitted from to_dict() when 0.
    # tidal_stress_factor: floor(tidal_amplitude_m / 10); omitted from to_dict() when 0.
    # total_seismic_stress: RSS + Tidal Seismic Stress + TSF.
    # seismic_temperature_k: ⁴√(mean_temp⁴ + TSS⁴); only when TSS>0 and value differs.
    # tidal_amplitude_m: combined surface tidal amplitude in metres (star + moons).

    # method: .to_dict()
    # keys: composition, diameter_km, density_g_cm3, mass_earth,
    #       gravity_g, escape_velocity_km_s, axial_tilt_deg, day_length_hours,
    #       tidal_status[, eccentricity_adjusted][, mean_temperature_k]
    #       [, tidal_amplitude_m][, residual_seismic_stress]
    #       [, tidal_seismic_stress (only when >0)][, tidal_stress_factor (only when >0)]
    #       [, total_seismic_stress][, seismic_temperature_k]  ← all only when not None
```

---

## `BeltPhysical` (`traveller_belt_physical.py`)

```python
@dataclass
class BeltPhysical:    # pylint: disable=too-many-instance-attributes
    inner_au: float       # inner boundary of belt span
    outer_au: float       # outer boundary of belt span
    m_type_pct: int       # metallic percentage
    s_type_pct: int       # silicate (rocky) percentage
    c_type_pct: int       # carbonaceous percentage
    other_pct: int        # residual "other" percentage (m+s+c+other == 100)
    bulk: int             # belt bulk (2D2+DMs, min 1)
    resource_rating: int  # resource rating (clamped to [2, 12])
    size_1_bodies: int    # count of Size 1 significant planetoids
    size_s_bodies: int    # count of Size S significant planetoids

    # method: .to_dict()
    # keys: inner_au, outer_au, m_type_pct, s_type_pct, c_type_pct, other_pct,
    #       bulk, resource_rating, size_1_bodies, size_s_bodies
```

---

## `WorldDetail` (`traveller_world_detail.py`)

Uses `__slots__` for memory efficiency (not a dataclass).

```python
class WorldDetail:
    sah: str            # 3-char Size/Atmosphere/Hydrographics; "000" for belts
    population: int     # 0 = uninhabited
    government: int
    law_level: int
    tech_level: int
    spaceport: str      # Y/H/G/F for secondaries; "-" for gas giants
    moons: list         # List[Moon], populated by attach_detail()
    trade_codes: list   # List[str]; empty for gas giants and rings
    physical: Optional[BeltPhysical]  # set by generate_system_detail() for belt slots; None otherwise
    biomass_rating: Optional[int]     # set by _apply_biomass() at end of attach_detail();
                                      # None for gas giants, belts, and empty slots;
                                      # 0 = no native life; positive = life present

    # computed properties:
    # .inhabited -> bool
    # .is_gas_giant -> bool  (True if sah starts with "GS", "GM", or "GL")
    # .profile -> str        (see Profile string formats below)

    # method: .to_dict()  — includes "physical": belt_physical.to_dict() or None
    #                        includes "biomass_rating": int when not None
```

---

## `Moon` (`traveller_moon_gen.py`)

```python
@dataclass
class Moon:  # pylint: disable=too-many-instance-attributes
    size_code: int | str        # int 0-15, or "S"; 0 + is_ring=True → ring
    is_ring: bool = False
    is_gas_giant_moon: bool = False  # moon is itself a small gas giant
    detail: Optional[WorldDetail] = None  # populated by attach_detail()
    _ring_count: int    # field(default=1, init=False) — set by _consolidate();
                        # not in __init__; use field() to keep type checkers happy

    # Orbit placement fields (all field(default=..., init=False)):
    orbit_pd: Optional[float]           # orbital distance in Planetary Diameters
    orbit_km: Optional[float]           # orbit_pd × planet_diameter_km
    orbit_range: Optional[str]          # "inner"|"middle"|"outer"|"excess"
    orbit_period_hours: Optional[float] # √(orbit_km³ / mass_earth) / 361730
    ring_centre_pd: Optional[float]     # rings only: 0.4 + roll(2)/8
    ring_span_pd: Optional[float]       # rings only: roll(3)/100 + 0.07
    orbit_eccentricity: float           # default 0.0; rolled via roll_eccentricity() when orbit placed
    orbit_inclination: float            # default 0.0; rolled via roll_inclination(); >90° = retrograde

    # properties: .size_str
```

All orbit placement fields default to `None` (or 0.0/False for scalars) until
`generate_moons()` is called with `orbit_au` and `star_mass_solar` provided.
`to_dict()` omits orbit fields that are `None`.

---

## HZ deviation sign convention

**Negative deviation** = orbit is closer to the star than HZCO = **warmer**.  
**Positive deviation** = orbit is further from the star than HZCO = **cooler**.

This matches the WBH Habitable Zones Regions table (p.46):

| Raw 2D roll | HZ deviation     | Zone      |
|-------------|------------------|-----------|
| 2−          | +1.1 or more     | Frozen    |
| 3           | +1.00            | Cold      |
| 4           | +0.50            | Cold      |
| 5           | +0.20 to +0.49   | Temperate |
| 6–9         | −0.20 to +0.19   | Temperate |
| 10          | −0.50 to −0.21   | Hot       |
| 11          | −1.00            | Hot       |
| 12+         | −1.1 or less     | Boiling   |

`generate_temperature_from_orbit()` in `traveller_system_gen.py` converts HZ
deviation to the raw CRB temperature roll and applies atmosphere DMs. Moons use
their **parent planet's** HZ deviation, not their own position.

---

## Orbit# vs AU — critical note

The WBH Orbit# scale is **non-linear** with respect to AU. Conversion is in
`_orbit_to_au()` in `traveller_stellar_gen.py` (also imported by
`traveller_orbit_gen.py`).

| Orbit# | AU    |
|--------|-------|
| 0      | 0.2   |
| 1      | 0.4   |
| 2      | 0.7   |
| 3      | 1.0   |
| 4      | 1.6   |
| 5      | 2.8   |
| 6      | 5.2   |
| 7      | 10.0  |
| 8      | 20.0  |
| 9      | 40.0  |
| 10     | 77.0  |
| 17     | 8512  |

**Never use Orbit# values directly as radial distances on an AU-scaled diagram.**
Always call `_orbit_to_au()` first.

---

## Profile string formats

`WorldDetail.profile` returns a formatted display string. The format depends on
the body type:

| Body type | Format | Example | Notes |
|-----------|--------|---------|-------|
| Mainworld | `{port}{SAH}{PGL}-{TL}` | `C473574-8` | Standard CRB UWP |
| Inhabited terrestrial | `{port}{SAH}{PGL}-{TL}` | `F473510-7` | |
| Uninhabited terrestrial | `Y{SAH}000-0` | `Y473000-0` | Y = no spaceport |
| Inhabited belt | `{port}000{PGL}-{TL}` | `G000121-8` | SAH always 000 |
| Uninhabited belt | `Y000000-0` | `Y000000-0` | |
| Gas giant | `{SAH}` only | `GM9` `GS4` `GLB` | No port or social codes |
| Inhabited moon (size 2+) | `{port}{SAH}{PGL}-{TL}` | `F532320-6` | |
| Uninhabited moon (size 2+) | `Y{SAH}000-0` | `Y473000-0` | |
| Size S moon | `YS00000-0` | | Auto vacuum |
| Size 0–1 moon | `Y{size}00000-0` | `Y100000-0` | Auto vacuum |
| Ring | `R0{count}` | `R01` `R03` | |
| Empty slot | `---` | | |

**Spaceport codes for secondaries** (Y/H/G/F — different from mainworld A–X):

| Code | Equivalent starport | Facilities |
|------|---------------------|-----------|
| Y | X | No spaceport |
| H | E | Primitive installation |
| G | D | Basic facility, unrefined fuel |
| F | C | Good facility, unrefined fuel, minor repair |

**Gas giant SAH format:** `G{category}{diameter}` where category is S/M/L and
diameter is eHex-encoded Terran diameters (2–18). Example: `GL9` = Large gas
giant, 9× Terra's diameter.

**`canonical_profile` takes display priority** over `WorldDetail.profile` for
TravellerMap mainworld orbit slots. Without this, an uninhabited mainworld
(population = 0) would display as `Y{SAH}000-0` rather than its true UWP.
