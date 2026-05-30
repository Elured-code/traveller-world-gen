# Traveller World & System Generator — Full Pipeline

This document shows how every module in the project connects and what data flows
between them.

---

## Overview

The project has two entry points, three generation phases, and multiple output paths.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         ENTRY POINTS                                     │
├───────────────────────────┬──────────────────────────────────────────────┤
│   Procedural generation   │   TravellerMap (canonical) generation        │
│                           │                                              │
│  generate_full_system()   │  generate_system_from_map()                  │
│  traveller_system_gen.py  │  traveller_map_fetch.py                      │
│                           │         │                                    │
│                           │         ▼                                    │
│                           │   HTTP → travellermap.com API                │
│                           │   canonical UWP, stellar string,             │
│                           │   bases, trade codes, PBG                    │
│                           │         │                                    │
│                           │         ▼                                    │
│                           │   parse stellar string → StarSystem          │
│                           │   generate_system_from_canonical()           │
└───────────────────────────┴──────────────────────────────────────────────┘
                                        │
                    ────────────────────┘
                    │
                    ▼
```

---

## Phase 1 — Stellar generation

```
traveller_stellar_gen.py
────────────────────────
generate_stellar_data()

  Roll primary spectral type + luminosity class (WBH pp.14-15)
  Interpolate mass, temperature, diameter from tables (WBH pp.17-19)
  Compute luminosity via Stefan-Boltzmann: L = D² × (T/T☉)⁴
  Determine system age (WBH pp.20-22)
  Roll companion stars: close, near, far (WBH pp.23-27)
  Each companion: type (random / lesser / sibling / twin) + physical properties

         │
         ▼
    StarSystem
    ├── stars: List[Star]     ← index 0 = primary
    │   ├── designation       "A", "B", "Ca", ...
    │   ├── spectral_type     "G", "K", "M", "D", "BD"
    │   ├── lum_class         "V", "III", "Ia", "D", "BD"
    │   ├── mass, temperature, diameter, luminosity
    │   ├── orbit_number, orbit_au  (0.0 for primary)
    │   ├── age_gyr, ms_lifespan_gyr
    │   └── orbit_period_yr, orbit_eccentricity, orbit_inclination
    └── .primary → stars[0]
        .age_gyr → stars[0].age_gyr
```

---

## Phase 2 — Orbit generation

```
traveller_orbit_gen.py
──────────────────────
generate_orbits(star_system, orbital_eccentricity, orbital_inclination)

  Roll world counts: gas giants, belts, terrestrials (WBH pp.36-37)
  Compute MAO (Minimum Allowable Orbit#) from star type/class table
  Compute HZCO = √luminosity  (Habitable Zone Centre Orbit#)
  Place baseline orbits, empty orbits, and spread across slots (Steps 3-6)
  Assign world types in order: empty → gas giant → belt → terrestrial (p.51)
  Select mainworld candidate (p.51)
  Roll anomalous orbits: eccentric, inclined, retrograde, trojan (Step 7)
  Roll orbital eccentricity and inclination values (Step 9, optional)

         │
         ▼
    SystemOrbits
    ├── stellar_system: StarSystem
    ├── gas_giant_count, belt_count, terrestrial_count, total_worlds
    ├── orbits: List[OrbitSlot]
    │   └── OrbitSlot
    │       ├── star_designation, orbit_number, orbit_au, slot_index
    │       ├── world_type   "gas_giant" | "terrestrial" | "belt" | "empty"
    │       ├── hz_deviation, temperature_zone, is_habitable_zone
    │       ├── is_mainworld_candidate
    │       ├── gg_sah, canonical_profile, anomaly_type, notes
    │       ├── orbit_period_yr, eccentricity, inclination
    │       └── detail: Optional[WorldDetail]  ← None until Phase 3
    ├── mainworld_orbit: Optional[OrbitSlot]
    └── star_mao / star_hzco / star_hz_inner / star_hz_outer  (per designation)
```

---

## Phase 2b — Mainworld generation

```
traveller_world_gen.py                    traveller_hydro_detail.py
──────────────────────                    ─────────────────────────
generate_world(name, ...)                 generate_hydrographic_detail()

  generate_size()                           surface_liquid_pct (random in code range)
  generate_atmosphere(size)                 fluid_type by temperature zone
  generate_atmosphere_detail()   ─────────► HydrographicDetail
    pressure_bar, oxygen_ppo,                └── stored as World.hydrographic_detail
    scale height, taints,
    gas mix, unusual subtypes
    └── stored as World.atmosphere_detail
  temperature_category(atmosphere, raw_roll)
    raw_roll = generate_temperature_from_orbit(hz_deviation)  ← not a free dice roll;
                                                                orbit position drives temp
  generate_hydrographics(size, atmosphere, temperature)
  generate_hydrographic_detail() ──────────────────────────────────────────────────────►
  generate_population()
  generate_government(population)
  generate_law_level(government)
  generate_starport(population)
  generate_tech_level(...)
  generate_bases(starport)
  assign_trade_codes(...)
  assign_travel_zone(...)

         │
         ▼
    World  (mainworld UWP)
    ├── name, size, atmosphere, temperature, hydrographics
    ├── population, government, law_level, starport, tech_level
    ├── has_gas_giant, gas_giant_count, belt_count
    ├── bases, trade_codes, travel_zone, notes, population_multiplier
    ├── atmosphere_detail:    Optional[AtmosphereDetail]
    ├── hydrographic_detail:  Optional[HydrographicDetail]
    │
    │   ← all fields below are None/False until Phase 3
    ├── size_detail:          Optional[WorldPhysical | BeltPhysical]
    ├── biomass_rating, biocomplexity_rating
    ├── native_sophont, extinct_sophont
    ├── biodiversity_rating, compatibility_rating
    └── lifeform_profile
```

---

## Phase 2 assembly

```
traveller_system_gen.py
───────────────────────
TravellerSystem(
    stellar_system = StarSystem,
    system_orbits  = SystemOrbits,
    mainworld      = World,
    mainworld_orbit = OrbitSlot,
)

Note: for TravellerMap systems, World.starport / .trade_codes / .travel_zone
are overridden with canonical values after generate_world() returns.
```

---

## Phase 3 — Detail attachment (optional)

```
traveller_world_detail.py
─────────────────────────
attach_detail(system, nhz_atmospheres, use_oxygen_rules,
              advanced_temp, runaway_greenhouse)

┌─ For every non-empty OrbitSlot ──────────────────────────────────────────┐
│                                                                          │
│  _generate_sah(world_type, orbit, star, ...)                             │
│      SAH = size / atmosphere / hydrographics for this slot               │
│                                                                          │
│  Social rolls (if terrestrial and population possible):                  │
│      population, government, law_level, tech_level, spaceport            │
│      assign_trade_codes()                                                │
│                                                                          │
│  traveller_moon_gen.py ──────────────────────────────────────────────────┤
│  generate_moons(world_detail, orbit_number)                              │
│      Roll moon count by world size / type (WBH p.56)                    │
│      Roll each moon's size (R / S / 1-G)                                │
│      place_moon_orbit() → orbit_pd, orbit_km, period_hours              │
│      roll_eccentricity(), roll_inclination()                             │
│      → List[Moon]  stored as WorldDetail.moons                          │
│                                                                          │
│  traveller_belt_physical.py  (belt slots only) ─────────────────────────┤
│  generate_belt_physical(orbit_slot, star, system_orbits, mainworld)      │
│      span (AU), composition (m/s/c/other %), bulk, resource_rating       │
│      size_1_bodies, size_s_bodies, mean_temperature_k                   │
│      → BeltPhysical  stored as WorldDetail.physical                     │
│                                                                          │
│  OrbitSlot.detail = WorldDetail                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌─ For the mainworld ───────────────────────────────────────────────────────┐
│                                                                           │
│  traveller_world_physical.py                                              │
│  generate_world_physical(world, orbit_slot, star, system_age_gyr)        │
│      Composition + density → mass, gravity, escape velocity (WBH p.75-76)│
│      Axial tilt (WBH p.77)                                               │
│      Day length + tidal lock status (WBH pp.103-107)                     │
│      → WorldPhysical  stored as World.size_detail                        │
│                                                                           │
│  generate_advanced_mean_temperature(...)  [if advanced_temp=True]        │
│      albedo (surface type + atmosphere + hydrographics)                  │
│      greenhouse_factor (atmosphere pressure + type)                      │
│      T = 279 × ⁴√(L × (1-A) × (1+G) / AU²)                            │
│      high/low temperature from tilt × rotation × geography               │
│      → sets WorldPhysical.advanced_mean_temperature_k, etc.              │
│                                                                           │
│  apply_moon_tidal_effects(world, moons)  [after moon generation]         │
│      Recalculate day length for moon tidal stress                        │
│      Recalculate stellar_day_hours                                       │
│                                                                           │
│  _apply_biomass(mainworld, age_gyr)                                      │
│      generate_biomass_rating(atm, temp, age, ...)                        │
│          WBH p.127: 2D + atmosphere DM + temperature DM + age DM         │
│          → World.biomass_rating                                           │
│                                                                           │
│      [skip remaining if biomass == 0]                                     │
│                                                                           │
│      generate_biocomplexity_rating(biomass, atm, age, ...)               │
│          WBH p.129: 2D−7 + min(biomass,9) + DMs                          │
│          → World.biocomplexity_rating                                     │
│                                                                           │
│      generate_sophont_checks(biocomplexity, age_gyr)  [if bio ≥ 8]      │
│          Current sophont: 2D + min(bio,9) − 7 ≥ 13                       │
│          Extinct sophont: same + DM+1 if age > 5 Gyr                     │
│          → World.native_sophont, World.extinct_sophont                    │
│                                                                           │
│      generate_biodiversity_rating(biomass, biocomplexity)                │
│          WBH p.130: max(0, 2D−7 + M + ⌈X/2⌉)                           │
│          → World.biodiversity_rating                                      │
│                                                                           │
│      generate_compatibility_rating(biocomplexity, atm, age, has_taint)  │
│          WBH p.130: max(0, 2D − ⌊X/2⌋ + _ATM_COMPAT_DM + age DM)       │
│          → World.compatibility_rating                                     │
│                                                                           │
│      lifeform_profile = eHex(M) + eHex(X) + eHex(D) + eHex(C)          │
│          → World.lifeform_profile                                         │
│                                                                           │
│  traveller_belt_physical.py  (belt mainworld only)                        │
│  generate_belt_physical(mw_orbit, ...)                                    │
│      → BeltPhysical  stored as World.size_detail                         │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Output paths

```
TravellerSystem / World
        │
        ├── .to_dict()  ──────────────────────────────► Python dict (JSON-ready)
        │   .to_json()  ──────────────────────────────► JSON string / file
        │
        ├── .to_html()  ──► html_render.py (Jinja2)  ► HTML card
        │                   templates/
        │                   ├── world_card.html      (mainworld detail card)
        │                   ├── system_card.html     (full system overview)
        │                   ├── world_list.html      (compact orbit table)
        │                   └── system_detail.html   (secondary world list)
        │
        ├── system_map.py ──────────────────────────► SVG orbit diagram
        │   build_system_map_svg(system, name, width)
        │   ├── _arc_path()      orbit arc geometry
        │   ├── _marker_xy()     world glyph position (1/3 down arc)
        │   └── _orbit_half_deg() arc sweep angle
        │
        └── gen-ui/app.py ───────────────────────────► PySide6 GUI
            QWebEngineView displays HTML cards
            SVG system map displayed in second tab
            File menu: Save As (JSON/HTML), Open JSON
```

---

## Serialisation and round-trip

Every major data class has `to_dict()` and `from_dict()` methods, enabling
complete save/restore of any generated system:

```
                    to_dict() / to_json()
  TravellerSystem ─────────────────────────► JSON file
        ▲                                         │
        │                 from_dict()             │
        └─────────────────────────────────────────┘

Reconstruction chain (from_dict calls from_dict down the tree):

  TravellerSystem.from_dict(d)
      ├── StarSystem.from_dict(d)
      │       └── Star.from_dict(s) × N
      ├── SystemOrbits.from_dict(d, star_system)
      │       └── OrbitSlot.from_dict(o) × N
      │               └── WorldDetail.from_dict(detail_d)   [if present]
      │                       ├── Moon.from_dict(m) × N
      │                       │       └── WorldDetail.from_dict(...)  [moon detail]
      │                       └── BeltPhysical.from_dict(phys_d)
      │                           WorldPhysical.from_dict(phys_d)
      └── World.from_dict(mainworld_d)
              ├── AtmosphereDetail.from_dict(atm_d)
              ├── HydrographicDetail.from_dict(hydro_d)
              └── WorldPhysical.from_dict(sd) / BeltPhysical.from_dict(sd)
```

---

## Supporting modules (no generation logic)

```
world_codes.py          tables.py            html_render.py
──────────────          ─────────            ──────────────
StarportCode (StrEnum)  SIZE_DIAMETER_LABEL  render(template, context)
TemperatureCategory     SIZE_GRAVITY_LABEL   Jinja2 template loader
TradeCode               POPULATION_RANGE     used by .to_html() on all
TravelZone              TRADE_CODE_FULL       World and TravellerSystem
AtmosphereCode (IntEnum)BASE_FULL             objects
APP_VERSION             ZONE_CSS_CLASS
                        TIDAL_STATUS_LABELS
                        BIOCOMPLEXITY_DESC

No imports of their own — safe to import from anywhere without
risk of circular dependencies.
```

---

## Module dependency graph

```
                      world_codes.py   tables.py   html_render.py
                            ▲              ▲              ▲
                            │              │              │
                    traveller_world_gen.py ◄──────────────┘
                            ▲
               ┌────────────┤
               │            │
traveller_hydro_detail.py   │
               ▲            │
               │    traveller_belt_physical.py
               │            ▲
               │            │
               │    traveller_world_physical.py
               │            ▲
               │            │
               └────────────┤
                            │
               traveller_stellar_gen.py
                            ▲
                            │
               traveller_orbit_gen.py
                            ▲
                            │
               traveller_system_gen.py ◄── traveller_map_fetch.py
                            ▲
                            │
               traveller_moon_gen.py ──────────────────────────┐
                            ▲                                  │
                            │                                  ▼
               traveller_world_detail.py ◄──────────────────────
                            ▲
                            │
                   ┌────────┴────────┐
                   │                 │
             gen-ui/app.py      system_map.py
             function_app.py
             traveller_map_fetch.py (render path)
```

---

## RNG seed flow

```
generate_full_system(seed=None)
        │
        ├── seed = seed or secrets.token_hex(4)   ← if no seed provided
        ├── random.seed(seed)                      ← global RNG initialised HERE
        │
        │   All subsequent dice rolls in the session draw from this state.
        │   The sequence is deterministic: same seed → same system.
        │
        ├── Phase 1: generate_stellar_data()       uses random.*
        ├── Phase 2: generate_orbits()             uses random.*
        ├── Phase 2b: generate_world()             uses random.*
        │
        └── Phase 3: attach_detail()               extends the same sequence
                (optional; skipping it changes the state for any later rolls)
```
