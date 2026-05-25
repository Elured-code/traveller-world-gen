# Traveller World Generator — v1.4.0 Release Notes

**1449 tests pass. Pylint 10.00/10.**

---

## Desktop App (gen-ui) Improvements

### Loading feedback for TravellerMap lookups

TravellerMap lookups now run on a background thread (`QThread`). The UI immediately shows `"Looking up <world> in <sector>…"` and disables the Generate button; the button re-enables when the response arrives. The app no longer freezes on slow connections or timeouts.

### System detail controls — visual hierarchy

The flat row of radio buttons and checkboxes has been replaced by a **System detail** group box (`QGroupBox`) with a built-in checkbox. When unchecked (the default), Qt automatically grays out the four child options — NHZ Atmospheres, Oxygen requires biomass, Advanced temperature, and Runaway greenhouse — making it immediately clear that these are sub-options. No more trial-and-error to discover the dependency.

### TravellerMap panel — show/hide instead of disable

When Procedural is selected, the Sector / Name / Hex fields are now hidden entirely rather than shown grayed out. The panel reappears when TravellerMap is selected.

### Orbit table — horizontal scroll

The system orbit survey table (11 columns including Ecc/Incl, Period, Notes) now scrolls horizontally when the panel is narrower than its content, rather than wrapping or overflowing. Column headers no longer wrap.

### System and Mainworld tabs

System results are shown in a two-tab layout:
- **System tab** — full system HTML (stellar data, orbit survey, all secondary worlds)
- **Mainworld tab** — world card HTML, selected by default when a mainworld exists

### Eccentricity and inclination always active

The separate "Orbital Eccentricity" and "Orbital Inclination" checkboxes have been removed. Both are now always computed when System detail is enabled, so the Ecc/Incl column is always populated.

---

## Physics and World Generation

### Advanced Mean Temperature (WBH pp.47–48)

Optional physics-based surface temperature computed from first principles:

```
T(K) = 279 × ⁴√( L × (1−A) × (1+G) / AU² )
```

- **L** — luminosity of all stars interior to the world's orbit
- **A** — rolled surface albedo based on composition and hz_deviation (rocky/icy/icy-far bands)
- **G** — rolled greenhouse factor scaled by surface pressure

Enabled by the **Advanced temperature** checkbox (requires System detail).

### High and Low Seasonal Temperatures (WBH pp.48–50)

The 9-step WBH procedure computes seasonal extremes from axial tilt, rotation rate, geographic distribution of surface liquid, orbital eccentricity, and atmospheric pressure. Displayed as High temperature and Low temperature in the world card.

### Stellar Day / Sidereal Day (WBH p.106)

The solar day (time between successive sunrises) is now distinguished from the sidereal rotation period. Formula: `1 / (1/day − 1/year_h)` for prograde; `1 / (1/day + 1/year_h)` for retrograde. Omitted for tidally locked worlds (star stationary in sky). Displayed as a separate "Stellar day" row in the World Body card.

### Runaway Greenhouse Rule (WBH p.79, optional)

Worlds with Atm 2–F and mean temperature > 303 K roll for runaway when the **Runaway greenhouse** checkbox is enabled. On a trigger, the atmosphere converts (Atm A/B/C), hydrographics are recalculated, and the advanced mean temperature is recomputed with the corrosive/insidious greenhouse multiplier. Requires Advanced temperature.

### Hydrographic Fluid Type (WBH pp.91–92)

The dominant surface liquid is now identified from the world's temperature zone:

| Temperature | Fluid |
|---|---|
| Boiling | Sulfuric Acid |
| Hot / Temperate | Water |
| Cold | Ammonia |
| Frozen | Liquid Hydrocarbons |

Desert worlds and gas/hydrogen atmosphere worlds carry no fluid type.

### Moon Orbit Eccentricity and Inclination (WBH p.76)

Significant moons now have orbital eccentricity and inclination rolled using the same tables as world orbits. Inclination > 90° indicates a retrograde orbit. Displayed in the Ecc/Incl column in moon sub-rows.

### Belt Mean Temperature

Asteroid belt worlds (Size 0) now show a **Mean temperature** in Kelvin, computed with the same WBH p.47 formula used for planetary worlds (atmosphere DM = 0 for belts).

---

## Native Life

### Biomass Rating (WBH pp.127–131)

Every terrestrial world and moon in a system now receives a biomass rating. The 2D roll uses DMs from atmosphere type, hydrographics, system age, and surface temperature. Biomass 0 = no native life; higher values indicate progressively complex ecosystems.

**Optional rule:** worlds with oxygenated atmospheres (Atm 2–9, D, E) can be required to have at least biomass 1 ("Oxygen requires biomass" checkbox).

### Biocomplexity Rating (WBH pp.127–131)

Worlds with non-zero biomass receive a biocomplexity rating — the most advanced organism type the ecosystem can support. Shown in the orbit table's Biosphere column (`B, C` — biomass eHex, biocomplexity eHex) and in the world card's Native life section.

### Native Sophonts (WBH p.131)

Worlds with biocomplexity ≥ 8 roll for the presence of a native sophont species:
- **Extant sophont** — 2D + min(biocomplexity, 9) − 7 ≥ 13
- **Extinct sophont** — same roll +1 DM if system age > 5 Gyr (only rolled when extant check fails)

Displayed in the world card's biological detail section.

---

## Seismic and Tidal Physics

### Seismic Stress (WBH pp.125–128)

Three components are now computed for every mainworld with physical detail:

- **Residual Seismic Stress (RSS)** — from world size, age, and significant moon sizes
- **Tidal Seismic Stress (TSS)** — from the primary star's orbital tidal force
- **Tidal Stress Factor (TSF)** — `floor(tidal_amplitude_m / 10)`

Total Seismic Stress = RSS + TSS + TSF. A Seismic Temperature is also computed when tidal heating measurably raises the baseline temperature.

### Surface Tidal Amplitude (WBH pp.107–108)

The combined tidal amplitude in metres from the primary star and all significant moons is computed and displayed in the World Body card.

### Gas Giant Satellite Tidal Stress (issue #74)

When the mainworld orbits a gas giant, the tidal stress calculation now correctly includes the dominant gas giant contribution in addition to the stellar contribution.

---

## Standalone Binaries (PyInstaller)

Pre-built executables are now available for all supported platforms. No Python installation required.

### Download

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `TravellerWorldGen-macos-arm64.zip` |
| macOS (Intel) | `TravellerWorldGen-macos-x86_64.zip` |
| Windows | `TravellerWorldGen-windows.zip` |
| Ubuntu | `TravellerWorldGen-ubuntu.tar.gz` |
| Fedora | `TravellerWorldGen-fedora.tar.gz` |

macOS builds are now architecture-native (arm64 / x86_64 separately), approximately half the size of a universal binary.

### macOS Gatekeeper

Binaries distributed without an Apple Developer certificate are quarantined. Recipients can bypass Gatekeeper once by right-clicking the `.app` and choosing **Open**, or clear the quarantine attribute before distributing:

```bash
xattr -cr TravellerWorldGen.app
```

### Reduced binary size

v1.4.0 binaries are substantially smaller than v1.3.0 through a combination of:

- 37 unused Qt modules excluded from the bundle
- Qt translation files removed (100+ languages not used by the app)
- Unused image format plugins removed (only SVG, JPEG, GIF, ICNS, ICO retained)
- Python bytecode optimised (`optimize=2` — docstrings and assertions stripped)
- Debug symbols stripped (`strip=True`) on Linux/macOS
- UPX compression enabled in CI on all platforms

---

## Bug Fixes

| Issue | Fix |
|---|---|
| #74 | Gas giant satellite mainworld tidal stress used star mass instead of gas giant mass |
| #64 | Anomalous orbit eccentricity DMs (Random +2, Eccentric +5, Inclined +2, Retrograde +2) were not applied |
| #63 | TravellerMap endpoints silently ignored `orbital_eccentricity` and `orbital_inclination` flags |
| #58 | Ecc/Incl column always showed `—` because checkboxes were not wired to the generate call |
| #52 | Belt counts for TravellerMap-fetched systems were off by one when the mainworld is a belt |
| Belt seismic | `apply_moon_tidal_effects()` crashed on belt mainworlds (Size 0) due to missing `WorldPhysical` attributes |
| Biomass temp | Two of the five WBH p.127 temperature DM rows (High temperature rows) were not applied |
| System HTML | `TravellerSystem.to_html()` was omitting `WorldPhysical` detail from the mainworld panel |
| TM fetch | `generate_system_from_map()` was not calling `generate_gas_mix()` or `generate_unusual_subtype()` |

---

## JSON Schema

New and updated fields in `traveller_world_schema.json`:

| Field | Type | Location |
|---|---|---|
| `mean_temperature_k` | integer | `BeltPhysical` |
| `stellar_day_hours` | number | `WorldPhysical` |
| `runaway_greenhouse` | boolean | `WorldPhysical` |
| `advanced_mean_temperature_k` | number | `WorldPhysical` |
| `high_temperature_k` | number | `WorldPhysical` |
| `low_temperature_k` | number | `WorldPhysical` |
| `albedo` | number | `WorldPhysical` |
| `greenhouse_factor` | number | `WorldPhysical` |
| `tidal_amplitude_m` | number | `WorldPhysical` |
| `tidal_stress_factor` | integer | `WorldPhysical` |
| `biomass_rating` | integer | `World` |
| `biocomplexity_rating` | integer | `World` |
| `native_sophont` | boolean | `World` |
| `extinct_sophont` | boolean | `World` |
| `fluid_type` | string | `HydrographicDetail` |

---

## Test Coverage

| Version | Tests |
|---|---|
| v1.2.0 baseline | 1146 |
| v1.4.0 | **1449** |

All 1449 tests pass.
