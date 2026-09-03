# stellar-orbit.md — traveller_stellar_gen.py and traveller_orbit_gen.py

Read this when working on stellar generation, orbit placement, HZCO/MAO
calculations, the Orbit# coordinate system, or anything that touches gas giant
SAH rolls at orbit-gen time.

See `context/data-structures.md` for `Star`, `StarSystem`, `OrbitSlot`,
and `SystemOrbits` dataclass definitions.

---

## traveller_stellar_gen.py — WBH pp. 14–29

### Public API

```python
system: StarSystem = generate_stellar_data(rng=None, unusual_stars=False)
```

When `unusual_stars=True`, the Unusual column (WBH p.219) is used instead of
the Special column for primary type determination on a roll ≤ 2. This can
produce NS, PSR, BH, or environment types (Nebula, Protostar, Star Cluster,
Anomaly). Routing (Issue #184, Session 200):

- **Protostar** → `_generate_protostar()` (full WBH p.219 rules; Class V, age 0.001–0.009 Gyr)
- **Nebula** → `_generate_young_star_env()` (Class V, cluster age ≤ 1.80 Gyr, no worlds)
- **Star Cluster** → `_generate_young_star_env()` (Class V, cluster age ≤ 1.80 Gyr, worlds normal)
  then `_roll_star_cluster_meta(age_gyr, star)` → stored in `_pending_star_cluster` (module sentinel),
  transferred to `StarSystem.star_cluster` inside `generate_stellar_data()`
- **Anomaly** → Giants fallback (referee-defined; Class Ia/Ib/II/III, no worlds)

Post-stellar remnant helpers (all module-private):

- `_wd_temperature(age_gyr, mass)` — interpolates WD temperature from
  `_WD_AGING_TABLE` (0–13 Gyr for 0.6 ☉), scaled by `mass / 0.6`.
- `_characterize_white_dwarf(age_gyr)` — rolls WD mass, diameter, temp, lum.
- `_characterize_neutron_star(age_gyr)` — rolls NS mass/diameter; uses WD aging
  for temperature approximation.
- `_characterize_black_hole()` — rolls BH mass (exploding 1D); returns
  Schwarzschild diameter and schwarzschild_km; temperature = 0.
- `_generate_protostar(designation, role="primary")` — full WBH p.219 protostar rules:
  Star Type table DM+1 → Class V; mass ±50%; diameter Class V × (1 + (2D−2)/10);
  luminosity recomputed from diameter; age 0.001–0.009 Gyr (primary only). Companions
  in a protostar system also call this function (WBH: all stars are protostars).
- `_generate_peculiar_star(designation, spectral, lum_class)` — dispatcher
  called by `generate_primary_star()` for `_PECULIAR_*` sentinel spectral values.
  Routes Protostar → `_generate_protostar()`; Nebula/Star Cluster →
  `_generate_young_star_env()`; Anomaly → Giants fallback.
- `_generate_cluster_age()` — rolls 1D×1D×50 Myr → Gyr (max 1.80 Gyr); shared by
  Nebula and Star Cluster generators.
- `_generate_young_star_env(designation, notes)` — young Class V star for Nebula/
  Star Cluster; uses cluster age + DM+1 to Star Type table when age < 0.2 Gyr.
- `_roll_star_cluster_meta(age_gyr, primary) → StarCluster` — rolls Star Cluster
  metadata (WBH p.219, issue #182): single-hex (1D<4) vs multi-hex; hex_diameter (1D+1
  for multi-hex); system_count (2D+5, range 7–17); merged_star flag
  (`primary.ms_lifespan_gyr < age_gyr`); jump_restriction ("Jump-2 minimum" for multi-hex).
  Called inside the Star Cluster branch of `_generate_peculiar_star()`; result stored in
  module sentinel `_pending_star_cluster` and transferred to `StarSystem.star_cluster`
  at the end of `generate_stellar_data()`.

**NS/PSR/BH spectral types** use `lum_class` matching `spectral_type`:
`Star(spectral_type="NS", lum_class="NS")` etc.
`Star.classification()` returns the spectral_type string directly for these.
`Star.bh_schwarzschild_km` (Optional[float], `init=False`) is set only for BH.

**Non-primary WDs** (from `_build_star()`) use `_characterize_white_dwarf(5.0)`
with a default age of 5.0 Gyr. NS/PSR/BH are currently only generated as primaries.

### Internal functions of note

- `_star_properties(spectral, subtype, lum_class)` — interpolates mass,
  temperature, and diameter from lookup tables.
- `_determine_non_primary_type(parent, role)` — determines type
  (Random / Lesser / Sibling / Twin) and generates the non-primary star.
- `_orbit_to_au(orbit_num)` — converts Orbit# to AU using the WBH table.
  **Also imported by `traveller_orbit_gen.py`** — do not rename or move without
  updating both files.

### Key design decisions

**Mass ordering invariant.** The primary star is always the most massive.
Non-primary star types are determined by comparing `candidate.mass > parent.mass`
directly — not by spectral letter alone. M0 V (0.50 M☉) and M7 V (0.12 M☉)
share the letter "M" but have very different masses. Comparing by letter was a
compliance bug fixed early in development.

**Companion vs secondary stars.** Companion stars share the same `orbit_number`
as their parent and have `role="companion"`. Their designation is the parent's +
a lowercase letter (parent `"A"` → companions `"Aa"`, `"Ab"`). Close/Near/Far
secondary stars have `role` set to their separation type and a separate
`orbit_number`.

---

## traveller_orbit_gen.py — WBH pp. 36–51

### Public API

```python
orbits: SystemOrbits = generate_orbits(system: StarSystem,
                                       cluster: Optional[StarCluster] = None, ...)
mao: float = get_mao(star: Star)
hzco: float = get_hzco(star: Star, combined_lum: Optional[float])
n: int = count_stars_orbited(orbit: OrbitSlot, stellar_system: StarSystem)
exists: bool = dead_star_system_exists(primary: Star, star_system: StarSystem, rng=None)
```

**`cluster` parameter (issue #182, Session 201):** When `cluster.merged_star` is True,
reduced world counts apply (GG/belt absent on roll(2,−2)≥6; terrestrials max(0,1D−2))
and eccentricity DM+2 is added to all eccentricity rolls. Passed through from
`generate_full_system()` / `generate_system_from_world()` as `cluster=stellar.star_cluster`.

**Empty-system environment guard (Session 200, Issue #184):**
Before the dead-star existence check, `generate_orbits()` tests
`any(env in primary.special_notes for env in ("Protostar", "Nebula", "Anomaly"))`.
If True, it returns an empty `SystemOrbits` immediately — no world count rolls fire.
Star Cluster does **not** trigger this guard; its planetary system generates normally.

**`dead_star_system_exists(primary, star_system, rng=None) → bool` (Session 196, WBH p.219):**
Called by `generate_orbits()` before world count rolls whenever the primary is in
`_DEAD_STAR_TYPES = {"NS", "BH", "PSR", "D"}`. Rolls 2D + DMs (target ≥ 8; natural 12
always succeeds). DMs: multiple dead stars −2; NS/PSR primary −2; BH primary −4.
If False, `generate_orbits()` returns an empty `SystemOrbits` immediately.

**`get_mao(star) → float`:** returns 0.001 for NS/BH/PSR (flat WBH rule); 0.01 for D.

**Dead star world counts (Session 196):** Gas giants absent on 6+; belts absent on 6+;
terrestrials = max(0, 1D − 2). Normal rules apply for non-dead-star primaries.

**Radiation zones (Session 196):** After orbit placement, if `primary.spectral_type == "PSR"`,
all occupied `OrbitSlot` objects have `radiation_zone = True` set. `to_dict()` emits it
only when True; `from_dict()` restores it.

**`OrbitSlot.radiation_zone: bool = False`** (field, default False, `init=False`). PSR and
magnetar systems (PSR covers both in this model) set this on all inhabited/belt/GG slots.

**`count_stars_orbited(orbit, stellar_system) → int` (Session 193, WBH pp.105-106):**
Returns the number of stars gravitationally dominated by the given orbit slot — used
to apply the multi-star tidal stress DM (tidal stress floor reduced by 1 per additional
star orbited). Rules: worlds orbiting a secondary star (not the primary) always return 1
(circumsecondary S-type orbit). Worlds orbiting the primary return 1 + the count of
close/near/far secondaries whose `orbit_number` is less than the world's own
`orbit_number` (i.e., the secondaries whose gravity is also felt at that orbital radius).
Imported by `system_pipeline._apply_moon_tidal()` and `fastapi._apply_mainworld_moon_tidal()`.

### Gas giant SAH — `_gg_sah_roll()` and `OrbitSlot.gg_sah`

Gas giant SAH (GS/GM/GL + diameter digit) is rolled **at orbit-gen time** inside
`generate_orbits()` and stored in `OrbitSlot.gg_sah`. This is a critical design
decision with two motivations:

1. `generate_mainworld_at_orbit()` in `traveller_system_gen.py` needs the gas
   giant's diameter to constrain satellite size (`[1, gg_diameter-1]`). Importing
   `traveller_world_detail` to do this would create a circular import.
2. The SAH value must be the same whether it is accessed for satellite sizing
   (in `system_gen`) or for the detail table (in `world_detail`). Rolling once
   and sharing it ensures consistency.

`OrbitSlot.gg_sah` is an empty string for non-gas-giant orbit slots.

**Consequence:** The RNG sequence shifts for any system that contains a gas giant
whenever `_gg_sah_roll()` is invoked. This was accepted as an unavoidable cost
of correctness (Session 13).

### Gas giant mass — `_roll_gg_mass()` and `OrbitSlot.gg_mass_earth`

GG mass is rolled at orbit-gen time by `_roll_gg_mass(gg_category)` immediately
after the SAH roll and stored in `OrbitSlot.gg_mass_earth` (Optional[float]):

| Category | Formula | Range (M⊕) |
|----------|---------|------------|
| GS | 5 × (1D + 1) | 10–35 |
| GM | 20 × (3D − 1) | 40–340 |
| GL | D3 × 50 × (3D + 4) | 350–3,300 |

This replaces the old `gg_diameter ** 2` proxy used at all five call sites
(`function_app.py`, `gen-ui/app.py`, `traveller_world_detail.py` ×2,
`traveller_moon_gen.py` via `planet_mass_earth`). All call sites use a
legacy-safe fallback: `orbit.gg_mass_earth if not None else float(diam ** 2)`.

**⚠ Seed-breaking:** `_roll_gg_mass()` adds 1–2 dice rolls per gas giant in
`generate_orbits()`, before the eccentricity block. Seeds are not reproducible
across the Session 85 boundary for systems containing gas giants.

### `OrbitSlot.detail` is a typed field

`OrbitSlot.detail` is declared as `Optional["WorldDetail"] = field(default=None,
init=False)` with a `TYPE_CHECKING` guard import. Do not use `getattr(orbit,
"detail", None)` — access it directly as `orbit.detail`.

### Mainworld selection scoring

The best candidate orbit is the one with the lowest score on:
`(type_penalty + hz_penalty + temperature_penalty + star_penalty, abs(hz_deviation))`

- Terrestrial worlds score better than gas giants
- Habitable zone worlds score better than non-HZ
- Temperate > cold/hot > frozen > boiling
- Primary star worlds score better than secondary star worlds

### HZ deviation and temperature

See `context/data-structures.md` for the HZ deviation sign convention and the
raw-roll → temperature zone mapping table.

`_temp_zone()` in `traveller_orbit_gen.py` converts an unscaled HZ deviation
directly to a temperature zone string using the WBH HZ Regions table. **No
scaling factor is applied** — an earlier version scaled deviations for
sub-Orbit#1 positions, which produced grossly incorrect temperatures for dim M-
type stars. That scaling was removed in Session 12 (compliance fix).

### Companion star exclusion zone

WBH forbids primary-star worlds in the band `[companion_orbit − 1.0, companion_orbit + 3.0]`.
Two cases:

| Condition | Action |
|-----------|--------|
| `companion_orbit − 1.0 > mao` | Cap `max_o = min(max_o, companion_orbit − 1.0)` — normal inner zone exists |
| `companion_orbit − 1.0 ≤ mao` | Push `mao = max(mao, companion_orbit + 3.0)` — companion so close that no inner zone exists |

The second case was a compliance bug (Session 39): `excl ≤ 0` never triggered the
`max_o` cap, placing worlds inside the forbidden zone. Fix is the `else` branch in
`generate_orbits()` lines ~400–404; `star_mao[designation]` must also be updated
in-place because it is read again later in the same function.

### Orbital periods

`Star.orbit_period_yr` (Optional[float]) is computed in `generate_stellar_data()` after
all stars and ages are set. Formula: `√(AU³ / (M_central + m))` where `m` is the
star's own mass and `M_central` is the combined mass of what it orbits:

| Star role | M_central |
|-----------|-----------|
| primary | None (no period) |
| companion (Ab orbiting A) | parent.mass only |
| secondary (B orbiting Aab) | sum of masses of all stars with effective system orbit# < B.orbit# |

**Effective system orbit#** for the combined-mass calculation:
- primary: 0.0
- companion to primary (Ab): 0.0 (moves with parent)
- secondary (B, C, …): their own orbit_number
- companion to secondary (Ba): parent secondary's orbit_number

This means Ca's M_central includes Ba (since Ba's effective orbit = B's orbit 6.1 < Ca's
orbit 12.1). Implemented via `_eff_sysorn()` nested helper in `generate_stellar_data()`.

**No new dice rolls** — pure math computed after all dice are done. No seed disruption.

`_fmt_period(period_yr)` in both `system_map.py` and `gen-ui/app.py` (module level)
auto-scales to hours (`h`), days (`d`), or years (`y`) for display.

### World orbital periods

`OrbitSlot.orbit_period_yr` (Optional[float], `init=False`) is computed in
`generate_orbits()` after all slots are placed, using `P = √(AU³ / M_central)`:

- `M_central` = designated star mass + masses of companions to that star
  whose `orbit_au < orbit.orbit_au` (WBH: planets orbiting outside a companion
  include the companion in the central mass sum)
- Planet mass correction (WBH: `mE × 0.000003`) is omitted as negligible
- `None` for empty orbit slots

`OrbitSlot.to_dict()` emits `"orbit_period_yr"` when not None. Displayed in the
`system_map.py` Period column (world rows) and `gen-ui` System Orbits card.

---

### Anomalous orbits (WBH pp.49-50)

`generate_orbits()` rolls for anomalous orbit count after the main orbit placement:

| 2D result | Anomalous orbits |
|-----------|-----------------|
| ≤ 9 | 0 |
| 10 | 1 |
| 11 | 2 |
| 12 | 3 |

Each anomalous orbit adds a terrestrial world (or belt when `terrestrial_count ≥ 13`).
In multi-star systems, the star is chosen randomly from those with available orbit space.

**Anomaly types** (roll 2D):

| 2D | Type | `anomaly_type` value | Notes stored |
|----|------|---------------------|--------------|
| ≤7 | Random orbit | `"random"` | `"Random orbit"` |
| 8 | Eccentric orbit | `"eccentric"` | `"Eccentric"` |
| 9 | Inclined orbit | `"inclined"` | `"Inclined XX°"` (1D+2)×10 + d10 |
| 10–11 | Retrograde orbit | `"retrograde"` | `"Retrograde"` |
| 12 | Trojan orbit | `"trojan_leading"` or `"trojan_trailing"` | `"Trojan leading (L4)"` etc. |

**Orbit# placement for random/eccentric/inclined/retrograde:** Roll 2D-2 + d10/10, clamped
within the star's valid zone (`star_avail[d]` inner zone or `star_outer[d]` outer zone
chosen 50/50 via 1D ≥ 4). Zone bounds are narrowed by ±0.01 to avoid landing exactly on
companion exclusion band boundaries. Retries up to 4× with ±1D adjustment on collision.

**Trojan placement:** Randomly pick an existing non-empty slot of the chosen star and
share its orbit#. Leading (L4) if 1D ≤ 3; trailing (L5) if 1D ≥ 4. Falls back to
"random" type if no non-empty host slots exist.

**Seed impact:** The `roll(2)` for anomalous count fires for every system — seed-breaking
from Session 41. Anomalous-orbit counts and types add further rolls when count > 0.

`OrbitSlot.anomaly_type` is `""` for all normal orbits. `OrbitSlot.to_dict()` emits
`"anomaly_type"` only when non-empty.

**Display:**
- `system_map.py`: suffix appended to type abbreviation — `_ANOM_SFXS` dict maps type →
  short label (e.g., `"terr R"`, `"terr L4"`)
- `SystemOrbits.summary()` and `TravellerSystem.to_html()`: anomaly notes shown in the
  notes/mw column when `o.anomaly_type` is set

---

### Primary star outer zone

When the inner zone exists (`companion − 1.0 > MAO`), the outer zone
`[companion + 3.0, 17.0]` is also valid territory for the primary. A `star_outer`
dict records this range during the availability loop. The placement loop wraps
the full baseline → spread → slot block in `for zone_mao, zone_max_o, zone_n,
zone_empty in zones`, running once for the inner zone and once (if populated) for
the outer zone. World types draw from the same shared pool in order.

Proportional allocation (`_avail_range()` nested helper in the multi-star branch)
sums inner + outer range for the primary, so worlds are distributed across all
three stars (A-inner, A-outer, B) in proportion to available orbital space.

Multiple companions: `outer_lo = max(companion + 3.0)` across all companions
with a valid inner zone, so the outer zone starts beyond the furthest exclusion
boundary. Seed-breaking for any system with a close/near/far companion that has
a valid inner zone (Session 39 cont.).

**`OrbitSlot.slot_index` is continuous across zones, not per-zone** (Session
167 compliance fix). The `for zone_mao, zone_max_o, zone_n, zone_empty in
zones:` loop builds a fresh local `slots` list per zone; a `slot_counter`
declared once per star *before* the zones loop (not `si+1` from each zone's
own `enumerate(slots)`) is what gets written to `OrbitSlot.slot_index`, so a
star with both an inner and outer zone gets one continuous `1..N` sequence
(previously reset to 1 for the outer zone). This isn't just display
numbering — `traveller_world_detail.py`'s `attach_detail()` keys its
`WorldDetail` results by `f"{star_designation}-{slot_index}"`, so a reset
meant two different orbit slots on the same star could collide on the same
key and silently overwrite each other's detail.

---

### Orbital eccentricity (WBH p.27)

Optional feature gated on `orbital_eccentricity: bool = False` parameter added to
`generate_orbits()` and `generate_full_system()`. When False (default), no new dice
rolls fire and all eccentricities remain 0.0.

When True, a post-placement pass in `generate_orbits()` calls `_roll_eccentricity()`
for each non-empty world/belt slot and each close/near/far secondary star.

**`_ECC_TABLE`** — six rows: `(max_first_roll, base, n_dice, divisor)`. Last row uses
sentinel 99 to catch all first-roll results ≥ 12.

**`_ANOM_ECC_DM`** — dict mapping `anomaly_type` → DM for the first roll of
`_roll_eccentricity()` (WBH pp.49-50):

| `anomaly_type` | DM |
|---|---|
| `"random"` | +2 |
| `"eccentric"` | +5 |
| `"inclined"` | +2 |
| `"retrograde"` | +2 |
| `"trojan_leading"` / `"trojan_trailing"` / `""` | 0 (absent from dict) |

**`_roll_eccentricity(orbit_number, system_age_gyr, extra_stars=0, is_belt=False, is_star=False, anomaly_dm=0)`**

Two-dice roll: first `roll(2, dm)` selects the table row; second `roll(n_dice) / divisor`
adds the fractional part. Result clamped to [0.000, 0.999].

DMs on the first roll only:

| Condition | DM |
|-----------|-----|
| Star orbits (is_star=True) | +2 |
| Each close/near/far companion with orbit# < slot orbit# (primary slots only) | +1 per star |
| Orbit# < 1.0 and system age > 1 Gyr | −1 |
| Belt slot | +1 |
| Anomalous orbit type (`anomaly_dm`) | per `_ANOM_ECC_DM` |

**`OrbitSlot.eccentricity`** — `field(default=0.0, init=False)`. `to_dict()` emits
`"eccentricity"`, `"orbit_au_min"`, `"orbit_au_max"` only when `eccentricity > 0`.

**`Star.orbit_eccentricity: float = 0.0`** — set for close/near/far stars by the same
post-placement pass. `Star.to_dict()` emits `"orbit_eccentricity"` and min/max AU
when non-zero.

**Min/Max separation:** `orbit_au × (1 ∓ eccentricity)`

**Display:** gen-ui "Ecc/Incl" column shows `0.350/—` when only eccentricity is set.
System map AU text shows `1.234 (e=0.35)`.

**Seed impact:** Flag False → no new dice, no seed disruption. Flag True → seed-breaking
(2 rolls per non-empty slot + 2 per secondary star).

---

### Orbital inclination (WBH p.28)

Optional feature gated on `orbital_inclination: bool = False` parameter added to
`generate_orbits()`, `generate_full_system()`, and `generate_system_from_world()`. When
False (default), no new dice fire and all inclinations remain 0.0.

When True, a post-placement pass in `generate_orbits()` calls `_roll_inclination()`
for each non-empty world/belt slot (except `anomaly_type == "inclined"` slots — they
already have an angle stored in `notes`) and each close/near/far secondary star.

**`_roll_inclination()`** — no table constant; each band uses a direct formula:

| 2D  | Band       | Formula                  | Range    |
|-----|------------|--------------------------|----------|
| 2–6 | Very Low   | `randint(1,6) / 2`       | 0.5–3°   |
| 7   | Low        | `randint(1,6)`           | 1–6°     |
| 8   | Moderate   | `roll(2)`                | 2–12°    |
| 9   | High       | `roll(2)*3 + randint`    | 7–42°    |
| 10  | Very High  | `(randint+1)*5 + randint`| 11–41°   |
| 11  | Extreme    | `roll(3)*5 − randint`    | 9–89°    |
| 12  | Retrograde | `max(0, 180 − _roll_inclination())` | ~91–179.5° |

Retrograde is recursive; terminates with probability 1.

**`OrbitSlot.inclination`** — `field(default=0.0, init=False)`. `to_dict()` emits
`"inclination"` (rounded to 2 dp) only when `inclination > 0`.

**`Star.orbit_inclination: float = 0.0`** — set for close/near/far stars by the same
post-placement pass. `Star.to_dict()` emits `"orbit_inclination"` when non-zero.

**Display:** gen-ui "Ecc/Incl" column shows combined `ecc_part/incl_part°` when either
or both are non-zero; `"—"` when both are zero. HTML orbit table `<th>` is `Ecc/Incl`.

**Seed impact:** Flag False → no new dice, no seed disruption. Flag True → seed-breaking
(1 roll minimum per eligible slot; recursive extra rolls for retrograde).
