# Traveller World Generator — v1.4.0 Release Notes

**2871 tests pass. Pylint 10.00/10.**

---

## pytest-qt GUI Test Suite (Session 124)

121 automated GUI tests in `tests/test_genui_app.py` covering the `gen-ui/app.py`
`AppWindow`, `_OptionsDialog`, `SystemMapWindow`, and `SurveyFormWindow`.

Key implementation details:

- **Module loading**: `gen-ui/app.py` is loaded via `importlib.util.spec_from_file_location("genui_app", path)` to avoid a name clash with `fastapi/app.py`
- **`_FakeSettings`**: in-memory stub for `QSettings` — no disk I/O during tests
- **`_MockWebView`**: `QWidget` subclass that captures HTML via `setHtml()` — never launches a Chromium subprocess
- **`QT_QPA_PLATFORM=offscreen`**: headless Qt rendering; `QTWEBENGINE_CHROMIUM_FLAGS=--log-level=3 --disable-gpu` suppresses Chromium noise
- **`isVisibleTo(parent)`** used instead of `isVisible()` for dialog sub-widgets (parent not shown)
- **`blockSignals` + `_seed_auto=False`** pattern used in reproducibility helpers to reliably set a seed value when the text field already holds the same string

13 test classes covering: initial state, name/seed fields, options dialog, generate triggers, output tabs, file menu, system map window, survey form window, dark mode, reproducibility, `_OptionsDialog` state, and integration tests.

pytest.ini gains `qt_api = pyside6` to configure pytest-qt bindings.

---

## Belt Profile Strings and IISS Survey Form (Session 123)

### `BeltPhysical.profile_str` (computed property)

New read-only property returning the WBH Class III belt shorthand:

```
S-CC.CC.CC.CC-B-R-#-s
```

where `S` = span in AU, `CC.CC.CC.CC` = M/S/C/O composition percentages
(dot-separated), `B` = bulk, `R` = resource rating, `#` = Size 1 body count,
`s` = Size S body count. Not emitted to JSON (`to_dict()` is unchanged).

### Belt profile in orbit tables

`system_body_table()` (text output) and `TravellerSystem.to_html()` (HTML orbit
table) both append `Profile: <profile_str>` to the Notes column for every belt
orbit slot that has a `BeltPhysical` attached.

### `TravellerSystem.to_survey_form_html()`

Renders `templates/survey_class0i.html` via Jinja2 and returns a self-contained
HTML page. Template data: `designation`, `age_gyr`, `stellar_count`, `star_rows`
(one dict per star with spectral data and orbital parameters), and `notes`
(footnote lines for sub-year periods in standard days).

### gen-ui Survey Form window

`SurveyFormWindow(title, html)` — a non-modal `QMainWindow` (980×700) containing
a `QWebEngineView`. `AppWindow` gains `_survey_btn`, `_survey_combo`, and
`_survey_windows` state. `_on_survey_clicked()` calls `_themed_html()` before
passing to `SurveyFormWindow` so the dark/light theme is applied.

### FastAPI — `survey_class0i_html` in JSON response

`/api/system/full` and `/api/map/system/full` now include a
`survey_class0i_html` key in the `include_mw_card` JSON response alongside
`sys_html` and `mw_html`.

---

## Injectable RNG for Deterministic Generation (Session 86, issue #42)

All generation modules now use injectable `random.Random` instances instead of the
global `random` module. This eliminates shared-state hazards on warm Azure Function
instances and enables fully isolated unit tests. Public entry-point functions accept
`rng: Optional[random.Random] = None`; `generate_full_system()` always creates a fresh
`random.Random(seed)` and propagates it through the entire pipeline. Seed reproducibility
is preserved — `random.Random(N)` uses the same Mersenne Twister as `random.seed(N)`.
`TravellerSystem` and `World` both gain a `seed` field emitted to JSON automatically,
removing the need for manual injection in API handlers.

---

## GG Moons Near the Roche Limit (Session 85, issue #120)

Four related bugs in the gas-giant satellite tidal-stress pipeline, exposed by seed
253115564 (which previously produced TSF 644, TSS 1,256,530 — physically impossible).

- **GG mass table:** New `_roll_gg_mass(gg_category)` rolls the WBH three-tier mass
  table (GS: 10–35 M⊕; GM: 40–340 M⊕; GL: 350–3,300 M⊕) and stores the result in
  `OrbitSlot.gg_mass_earth`. All five call sites updated; legacy files fall back to the
  old `diameter²` estimate.
- **TSS formula removed for GG satellites:** `_compute_tidal_ss` is calibrated for
  AU-scale distances; at moon distances it amplified results by ~10¹⁵×. The formula is
  no longer called for GG-satellite mainworlds; tidal amplitude contribution is kept.
- **TSF capped at 500:** Prevents overflow at the display layer and enforces a physical
  liquefaction ceiling on dissipation.
- **Perigee Roche limit check:** Any significant moon whose `orbit_pd × (1 − e) < 2.0`
  is tidally disrupted and converted to ring material after eccentricity rolls.

Seed result for 253115564: TSF 644 → 8; TSS 1,256,530 → 0; total SS 1,257,174 → 8.
**This is a seed-breaking change** — `_roll_gg_mass()` adds 1–2 dice rolls per gas
giant before the eccentricity block.

---

## gen-ui Dark Mode (Session 84, issue #81)

The **View › Dark Mode** menu item toggles a dark colour scheme for all native Qt
controls (main window, group boxes, labels, badges). The preference persists across
launches via `QSettings`. HTML world and system cards follow the in-app toggle
rather than the OS dark-mode setting, so the card and native UI always match.

---

## System Card Improvements (Session 83)

### MAO and HZ Orbit# in Stars Table (issue #115)

The Stars table now shows the **Minimum Armistice Orbit** (MAO) and **Habitable
Zone Orbit#** (inner – centre – outer) for each star. These values are pre-computed
at orbit-generation time and are now surfaced directly in the system HTML output.

### Mainworld Detail Removed from System Tab (issue #114)

The System tab no longer duplicates the mainworld's full world card content. UWP
statistics, atmosphere, hydrographic, biological, habitability, and notes now appear
exclusively on the Mainworld tab.

### Ammonia Fluid Type Fix (issue #116)

Cold worlds with standard breathable atmospheres no longer incorrectly display
Ammonia as the surface fluid. Ammonia oceans are now restricted to worlds with
exotic, corrosive, insidious, or unusual atmosphere codes (10–15), matching the
WBH pp.91–92 specification.

---

## Native Life (continued)

### Habitability Rating (WBH p.131, Sessions 80–82)

Every mainworld now receives a **Habitability Rating** — a deterministic score on a
0–10+ scale indicating how suitable the world is for unprotected human habitation.

- **Base 10** + DMs for size, atmosphere code, hydrographics, tidal lock, surface
  temperature, and gravity
- **Temperature path**: uses `advanced_mean_temperature_k` / `high_temperature_k`
  when advanced temperature is enabled; falls back to the CRB temperature category
  string ("Frozen", "Cold", "Hot", "Boiling") otherwise
- **Gravity DM** resolves WBH boundary ambiguity using a monotonic non-overlapping
  table; boundary values always take the worst (most negative) DM
- **Result clamped** to a minimum of 0
- Stored on both `World.habitability_rating` and `WorldDetail.habitability_rating`;
  emitted in JSON; displayed on the world card with a descriptive label

| Rating | Description |
|--------|-------------|
| 0 | Actively hostile world |
| 1–2 | Barely habitable world |
| 3–5 | Marginally survivable world |
| 6–7 | Regionally habitable world |
| 8–9 | Suitable for human habitation |
| 10+ | Terra-equivalent garden world |

### Seismic Heating Baked into Temperature (WBH pp.125–128, Session 80)

The `advanced_seismic_temperature_k` display field has been removed. Instead,
`_apply_seismic_stress()` updates `advanced_mean_temperature_k`, `high_temperature_k`,
and `low_temperature_k` **in place** using Stefan-Boltzmann superposition
(`T_total = ⁴√(T₁⁴ + T₂⁴)`). The seismic contribution is already included in the
temperatures shown on the world card.

### Very Cold World Temperature Fix (WBH p.47, Session 81)

The WBH p.47 footnote specifies that extrapolated mean temperatures below 10 K
should use `1D+5` (6–11 K) rather than the linear extrapolation. This edge case is
now correctly implemented in `_compute_mean_temperature()`.

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
| `habitability_rating` | integer | `World` |

Removed field: `advanced_seismic_temperature_k` (seismic heating now baked into
`advanced_mean_temperature_k` / `high_temperature_k` / `low_temperature_k`).

---

## Test Coverage

| Version | Tests |
|---|---|
| v1.2.0 baseline | 1146 |
| v1.4.0 (Sessions 55–79) | 1449 |
| v1.4.0 (Sessions 80–82) | 1644 |
| v1.5.0 (Sessions 88–112) | **1946** |
| v1.5.0 (Sessions 113–119) | **2044** |
| v1.5.0 (Sessions 120–124) | **2250** |

All 2250 tests pass.

---

---

# Traveller World Generator — v1.3.1

## Bug Fixes

- **Windows binary — web views blank**: `QtWebEngineProcess.exe` and WebEngine resource files (`.pak`, locales) were not bundled by PyInstaller when `PySide6-Addons` is installed separately from the base `PySide6` package. The System tab and any `QWebEngineView` rendered a blank white panel. Fixed by explicitly collecting these files in `traveller_gen_ui.spec`.

- **Windows — `ModuleNotFoundError: No module named 'PySide6.QtWebEngineWidgets'`**: `PySide6-Addons` (which provides `QtWebEngineWidgets`) was not listed in `gen-ui/requirements.txt`. Added `PySide6-Addons>=6.4.0` so it is installed alongside `PySide6` with a compatible version constraint.

## Documentation

- Added `docs/MACOS-GATEKEEPER.md` with step-by-step instructions for macOS users to bypass Gatekeeper, including a workaround for the archive extraction failure (`xattr -dr com.apple.quarantine` and `unzip` via Terminal).

---

# Traveller World & System Generator — v1.3.0

**Branch:** `v1.3.0` → `main` | **Sessions:** 55–68 | **Tests:** 1449 | **Pylint:** 10.00/10

---

## New Features

### Optional Runaway Greenhouse Rule (Session 68, WBH p.79)
- `check_runaway_greenhouse(atmosphere, temp_k, age_gyr, size)` in `traveller_world_physical.py` — pure function returning `Optional[RunawayGreenhouseResult]`
- Trigger: Atm 2–15 AND `advanced_mean_temperature_k > 303`; roll 2D + ⌈age_gyr⌉ + `(temp_k−303)//10` ≥ 12
- Case A (Atm A/B/C/F+): no code change, boiling hydrographic treatment. Case B (Atm 2–9/D/E): 1D selects A/B/C with size and taint DMs
- Post-runaway: atmosphere mutated, temperature set to `"Boiling"`, hydrographics recalculated, `generate_advanced_mean_temperature()` re-run
- `WorldPhysical.runaway_greenhouse: Optional[bool]`; emitted in JSON and displayed in world/system card
- gen-ui: `_maybe_apply_runaway_greenhouse()` method; "Runaway greenhouse" checkbox enabled under Full detail + Advanced temperature

### Advanced Mean Temperature, High/Low Temperature (Session 65, WBH pp.47–50)
- `generate_advanced_mean_temperature()` in `traveller_world_physical.py`
- Formula: `T(K) = 279 × ⁴√(L × (1−A) × (1+G) / AU²)`; albedo rolled by world type (rocky/icy/icy-far) with atmosphere and hydrographic modifiers; greenhouse factor from pressure scaled by atmosphere class
- High/low temperatures via 9-step seasonal variance procedure (axial tilt, rotation, geographic, luminosity modifier factors)
- New `WorldPhysical` fields: `albedo`, `greenhouse_factor`, `advanced_mean_temperature_k`, `high_temperature_k`, `low_temperature_k`
- Biomass temperature DM split: `generate_biomass_rating()` gains `high_temp_k` parameter; WBH p.127 rows 1–2 (high temp) now applied independently of rows 3–5 (mean temp)

### Hydrographic Fluid Type (Session 67, WBH pp.91–92)
- `HydrographicDetail.fluid_type: Optional[str]` — Water / Ammonia / Liquid Hydrocarbons / Sulfuric Acid by temperature zone; `None` for desert worlds and Gas/Hydrogen atmospheres
- Emitted in JSON; displayed in hydrographic detail card

### Stellar Day / Sidereal Day Correction (Session 66, WBH p.106)
- `WorldPhysical.stellar_day_hours: Optional[float]` — solar day computed from sidereal period and orbital period
- Handles prograde, retrograde, 3:2 resonance, and 1:1 lock cases; only set when orbital data available

### Biocomplexity Rating and Native Sophonts (Session 64, WBH pp.127–131)
- `generate_biocomplexity_rating()`: 2D−7 + min(biomass,9) + DMs (atmosphere, low-oxygen taint, age)
- `generate_sophont_checks()`: biocomplexity ≥ 8 rolls for current and extinct sophont presence
- `World.biocomplexity_rating`, `World.native_sophont`, `World.extinct_sophont` fields
- Biosphere column added to orbit table

### Moon Orbital Eccentricity and Inclination (Session 62, WBH p.76)
- Reuses world-orbit tables; `orbit_retrograde: bool` replaced by `orbit_inclination: float` (>90° implies retrograde)
- `orbit_eccentricity` and `orbit_inclination` emitted in JSON when non-zero

### Biomass Rating and Optional Oxygen Rule (Session 61, WBH pp.127–131)
- `generate_biomass_rating()` for all terrestrial worlds and moons; RNG appended at end of `attach_detail()` to preserve existing seeds
- Optional rule: `optional_biomass_rule=True` raises biomass to minimum 1 for oxygenated atmospheres

### Seismic Stress Pipeline (Sessions 56–60, WBH pp.125–128)
- Residual Seismic Stress, Tidal Seismic Stress, Tidal Stress Factor, Total Seismic Stress, Seismic Temperature
- Surface tidal amplitude in metres (star + moon contributions); `tidal_amplitude_m` and `tidal_stress_factor` on `WorldPhysical`

---

## gen-ui Changes

- **System tab** (issue #86): replaced `_build_stellar_card()` / `_build_orbits_card()` native Qt widgets (~273 lines) with `QWebEngineView` rendering `system.to_html()`
- **Radio toggle**: "Mainworld only" / "Full detail" radio buttons replace System/Mainworld detail checkboxes
- **Two-tab layout**: System tab (HTML) + Mainworld tab (world card HTML)
- **Removed**: "Orbital Eccentricity" and "Orbital Inclination" checkboxes (always calculated under Full detail)

---

## Infrastructure

- **PyInstaller** (`traveller_gen_ui.spec`): one-file spec bundling templates, PySide6 plugins, and all project modules; template path resolved via `sys._MEIPASS` when frozen
- **CI** (`.github/workflows/build-binaries.yml`): cross-platform builds for Windows, macOS (Intel + ARM), Ubuntu, Fedora on release creation; `workflow_dispatch` trigger for manual runs
- **Enum types** (`world_codes.py`, issue #38): `StarportCode`, `TemperatureCategory`, `TradeCode`, `TravelZone`, `AtmosphereCode`
- **Centralised display tables** (`tables.py`, issue #39): seven lookup tables consolidated from across five files
- **Pyright CI** (`.github/workflows/typecheck.yml`): runs on every push/PR to `main`

---

## Bug Fixes

- Biomass temperature DM−6 for boiling/frozen worlds was only applying DM−4 or DM−2 (rows 1–2 of WBH p.127 table were not applied)
- `apply_moon_tidal_effects()` crashed on belt mainworlds (`BeltPhysical` passed where `WorldPhysical` expected)
- Mainworld-as-moon row not bold in orbit table

---

## Tests

1449 tests across `tests/test_world_physical.py`, `tests/test_biomass.py`, `tests/test_moon_gen.py`, `tests/test_hydro_detail.py`, and others. All pass. Pylint 10.00/10 on all core modules.
