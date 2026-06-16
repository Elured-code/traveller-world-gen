# gen-ui User Acceptance Test Plan

**Application:** `gen-ui/app.py` — PySide6 desktop UI for the Traveller World & System Generator  
**Last updated:** 2026-06-15 (Session 123)  
**Test type:** Manual (no automated runner)

---

## Scope

Covers all interactive features of `AppWindow`, `SystemMapWindow`, and `SurveyFormWindow`
as of Session 123.  Backend generation logic is covered by the automated pytest suite;
this plan focuses on observable UI behaviour only.

## Environment

| Requirement | Detail |
|-------------|--------|
| Python | 3.11 via `.venv` |
| Launch | `.venv/bin/python gen-ui/app.py` from the repo root |
| macOS SSL | Run `Install Certificates.command` in the Python framework dir before testing TravellerMap lookups |
| Network | Tests in §6 (TravellerMap) require an active internet connection |

## How to record results

Fill in the **Result** column with **Pass**, **Fail**, or **Skip** (with a brief
note when failing or skipping).  Re-run failed cases after any fix and record the
re-run outcome alongside the original.

---

## 1. Startup

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-001 | Application launches without error | `.venv` active | Run `.venv/bin/python gen-ui/app.py` | Main window opens; no console traceback | |
| UAT-002 | Initial widget state | App just launched | Observe controls panel | "Procedural" radio selected; "TravellerMap" radio present; "Options…" button present; "Generate" button present; no inline system/mainworld checkboxes visible | |
| UAT-003 | Initial result panel shows onboarding card | App just launched | Observe result area | Onboarding placeholder card displayed; no world card or error visible | |

---

## 2. Controls and seed handling

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-004 | Auto-seed generated when seed field is empty | Procedural source; seed field empty | Click "Generate" | Seed field populated with a numeric value after generation | |
| UAT-005 | Manual seed is used when entered | Procedural source | Enter `12345` in seed field; click "Generate" twice | Both runs produce identical world name, UWP, and stats | |
| UAT-006 | "New Seed" button clears the seed | Seed field contains a value | Click "New Seed" | Seed field becomes empty; next generate uses a fresh seed | |
| UAT-007 | Non-integer seed shows error | Procedural source | Enter `abc` in seed field; click "Generate" | Error message "Seed must be an integer." displayed; no world generated | |
| UAT-008 | Return key in name field triggers generate | Procedural source; name field focused | Type a name; press Return | Generation runs as if "Generate" was clicked | |
| UAT-009 | Return key in seed field triggers generate | Procedural source; seed field focused | Type a valid integer; press Return | Generation runs as if "Generate" was clicked | |

---

## 3. Procedural world generation (world-only mode)

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-010 | World generated with custom name | Procedural; "System detail" unchecked in Options | Enter "Cogri" in name field; click "Generate" | World card displayed with name "Cogri" in header | |
| UAT-011 | World generated with empty name uses "Unknown" | Procedural; "System detail" unchecked; name field empty | Click "Generate" | World card header shows "Unknown" | |
| UAT-012 | Same seed reproduces identical world | Procedural; "System detail" unchecked | Generate with seed `99`; note UWP; click "New Seed"; enter `99`; generate again | UWP and all stats identical to first run | |
| UAT-013 | World card shows UWP in monospace | Any world result | Observe world card header | UWP string (e.g. `A867A69-F`) displayed in monospace font alongside world name | |
| UAT-014 | World-only result has no "System Map" or "Survey Form" buttons | Procedural; "System detail" unchecked | Generate a world | Neither "System Map" nor "Survey Form" button visible in result header | |

---

## 4. Options dialog

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-015 | Options… button opens modal dialog | App running | Click "Options…" | Modal dialog opens with checkboxes, radio buttons, and a settlement type group | |
| UAT-016 | System detail group expands to show six sub-options | Options dialog open; "System detail" unchecked | Check "System detail" | Sub-widget expands showing: NHZ Atmospheres, Oxygen requires biomass, Advanced temperature, Runaway greenhouse, Independent government, Select mainworld | |
| UAT-017 | Unchecking System detail collapses and clears sub-options | System detail checked with sub-options set | Uncheck "System detail" | Sub-widget collapses; all six sub-checkboxes are cleared | |
| UAT-018 | Population detail and Government detail are standalone checkboxes | Options dialog open | Observe below System detail group | "Population detail" and "Government detail" checkboxes present and enabled regardless of System detail state | |
| UAT-019 | Settlement type group has five radio buttons | Options dialog open | Observe Settlement type section | Five mutually-exclusive radio buttons: Standard, Long-settled, Well-settled, Backwater, Unsettled | |
| UAT-020 | Cancel discards changes | Options dialog open; settings modified | Change several options; click Cancel | Dialog closes; option state reverts to what it was before opening | |
| UAT-021 | OK saves changes; re-opening shows saved state | Options dialog open | Set options; click OK; click "Options…" again | Re-opened dialog shows the saved option state | |
| UAT-022 | Options persist across app restart | Options set and saved via OK | Quit and relaunch app | Options dialog re-opens with the previously saved settings | |

---

## 5. Procedural system generation

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-023 | System detail option enables full system generation | Options: "System detail" checked | Click "Generate" | Result contains Stellar System data and System Orbits table in addition to a Mainworld card; "System Map" and "Survey Form" buttons appear in the result header | |
| UAT-024 | System result shows System and Mainworld tabs | "System detail" checked; system generated | Observe result panel | Two tabs present: "System" (stellar + orbits) and "Mainworld" (world card); Mainworld tab active by default | |
| UAT-025 | System generation populates World Body card | Options: "System detail" checked; terrestrial mainworld | Observe Mainworld tab | "World Body" card present with diameter, gravity, density, and composition rows | |
| UAT-026 | Advanced temperature option produces Atmosphere Detail card | Options: "System detail" + "Advanced temperature" checked | Generate any system | Mainworld tab contains "Atmosphere Detail" card with Profile string, Pressure, and temperature rows | |
| UAT-027 | System Map button enabled after system generation | Options: "System detail" checked | Generate system; observe header | "System Map" button is present and enabled | |
| UAT-028 | Select mainworld option determines mainworld via scoring | Options: "System detail" + "Select mainworld" checked; fixed seed | Generate system; note mainworld designation | Mainworld may differ from the default first-terrestrial; result is deterministic for the same seed and options | |
| UAT-029 | Same seed and options produce identical system | Any option configuration | Generate with seed `42`; note UWP and orbit table; regenerate with seed `42` and same options | All outputs identical | |
| UAT-030 | Belt orbit Notes column shows WBH Class III profile string | "System detail" checked; generate until a belt orbit appears (or use a known seed) | Observe System Orbits table belt row; inspect Notes cell | Notes cell contains `Profile: S-CC.CC.CC.CC-B-R-#-s` in WBH Class III format | |
| UAT-031 | Population detail option adds city data to inhabited worlds | Options: "System detail" + "Population detail" checked; inhabited mainworld | Generate system | Mainworld card shows population detail section with PCR and major city list | |
| UAT-032 | Government detail option adds government structure data | Options: "System detail" + "Government detail" checked; inhabited mainworld | Generate system | Mainworld card shows government detail section; absent for government codes 0 and 7 | |

---

## 6. TravellerMap lookup

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-033 | Switching to TravellerMap source shows TM controls | Procedural selected | Click "TravellerMap" radio | TM-specific controls (Sector, World name, Hex fields) appear; procedural name/seed controls hidden | |
| UAT-034 | Name search returns world result | TravellerMap source; internet available | Enter sector "Spinward Marches", name "Regina"; click "Generate" | World card displayed for Regina with correct canonical UWP | |
| UAT-035 | Hex search returns world result | TravellerMap source; internet available | Enter sector "Spinward Marches", hex "1910"; click "Generate" | World card displayed for the world at hex 1910 | |
| UAT-036 | Generate without sector shows error | TravellerMap source; sector field empty | Click "Generate" | Error message "Sector is required for TravellerMap lookup." | |
| UAT-037 | Generate without name or hex shows error | TravellerMap source; sector entered; name and hex fields empty | Click "Generate" | Error message "Enter a world name or hex for TravellerMap lookup." | |
| UAT-038 | Ambiguous world name shows disambiguation dialog | TravellerMap source; internet available | Enter a sector and a name matching multiple worlds | Disambiguation dialog appears listing candidate worlds; selecting one proceeds to generation | |
| UAT-039 | TravellerMap result shows canonical UWP in orbit table | TravellerMap source; "System detail" checked; internet available | Fetch a known world | Mainworld orbit slot shows the canonical UWP from TravellerMap, not a procedurally generated one | |

---

## 7. World card display

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-040 | Stat row shows Starport, Size, Tech Level boxes | Any world result | Observe top of world card | Three stat boxes visible: Starport (code + quality label), Size (code + diameter), Tech Level (code + era badge) | |
| UAT-041 | Physical inner card shows atmosphere, temperature, hydrographics | Any world result | Observe "Physical" inner card | Rows for Atmosphere, Survival gear, Temperature, Hydrographics, Gas giants, Planetoid belts, PBG | |
| UAT-042 | Society inner card shows population, government, law, bases | Any world result | Observe "Society" inner card | Rows for Population, Government, Law level, Bases | |
| UAT-043 | Trade codes displayed as badges | World with trade codes | Observe trade code row | Each trade code shown as a coloured badge with full name (e.g. "Ag — Agricultural") | |
| UAT-044 | Notes section appears for worlds with generation warnings | Generate worlds until a note appears (or use a known seed) | Observe notes card | Notes group box present; each note listed with a bullet | |
| UAT-045 | Atmosphere Detail card shows profile and quantitative values | "System detail" + "Advanced temperature" checked; system generated | Observe "Atmosphere Detail" card | Card present with Profile string (e.g. `6-1.013-0.212`), Pressure, O₂ partial pressure, and Scale height rows | |
| UAT-046 | Atmosphere Detail card shows taint details | Generate until a tainted atmosphere (codes 2/4/7/9) appears | Observe "Atmosphere Detail" card | Taint rows present: subtype name, Severity description, Persistence description | |
| UAT-047 | Two taints show numbered labels | Generate until cascade taint occurs (rare; or use a known seed) | Observe taint rows | Labels read "Taint 1" and "Taint 2" rather than plain "Taint" | |

---

## 8. System view display

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-048 | Stellar card shows system age and star entries | "System detail" checked; system generated | Observe "System" tab → Stellar System card | System age in Gyr displayed; table rows for each star with designation, spectral type, mass, luminosity, orbit AU, and period | |
| UAT-049 | Orbit table shows all orbit slots | "System detail" checked | Observe "System" tab → System Orbits card | Rows for each orbit slot with star, orbit number, AU, ecc/incl, type, profile, HZ zone, period, and notes columns | |
| UAT-050 | Mainworld orbit slot identifiable in orbit table | System with mainworld | Observe orbit table | Mainworld slot shows the world's profile/UWP; distinguishable from secondary slots | |
| UAT-051 | System tab and Mainworld tab both present | System generated | Observe result panel tabs | Two tabs labelled "System" and "Mainworld"; "Mainworld" tab selected by default | |
| UAT-052 | Mainworld tab shows world card | System generated | Click "Mainworld" tab | World card for the mainworld displayed; UWP matches the orbit table mainworld entry | |
| UAT-053 | Gas giant mainworld shows satellite UWP in Mainworld tab | Generate until gas giant mainworld (or use a known seed) | Observe Mainworld tab | Displays the satellite world's UWP and characteristics, not the gas giant's profile | |
| UAT-054 | Belt orbit Notes column shows belt profile string | Generate system with a belt orbit (or use known seed) | Observe System Orbits belt row; Notes cell | Notes cell contains `Profile:` followed by the WBH Class III belt profile string | |

---

## 9. File menu

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-055 | File > Open JSON… loads a saved world | World JSON saved previously | File > Open JSON…; select file | World card rendered from loaded data; UWP and stats match the original | |
| UAT-056 | File > Open JSON… loads a saved system | System JSON saved previously | File > Open JSON…; select system JSON | "System" and "Mainworld" tabs restored; stellar and orbit data present | |
| UAT-057 | Version mismatch shows warning dialog with Yes/No choice | JSON saved under a different `_app_version` | File > Open JSON…; select old-version file | Warning dialog shows saved version vs current; choosing Yes proceeds; choosing No aborts | |
| UAT-058 | File > Save As… saves HTML | Any world or system result | File > Save As…; choose HTML format; confirm path | File saved; opening in browser shows the world/system card matching in-app display | |
| UAT-059 | File > Save As… saves JSON with `_app_version` key | Any world or system result | File > Save As…; choose JSON format; confirm path | Valid JSON file saved containing `name`, `uwp`, and `_app_version` fields | |
| UAT-060 | Saved JSON reloads without version warning | JSON saved via current app version | File > Open JSON…; select the just-saved file | World or system loads correctly; no version mismatch dialog | |
| UAT-061 | Generating a new world replaces the result panel | World result visible | Change name; click "Generate" | Previous result replaced by new world card; no duplication or console error | |

---

## 10. System Map window

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-062 | "System Map" button opens map window | System result visible; "System detail" was checked | Click "System Map" | A new `SystemMapWindow` opens displaying the SVG star system map in a web view | |
| UAT-063 | Map shows all system bodies | System map window open | Observe rendered SVG | Orbits and body types (gas giant, belt, terrestrial, empty) represented; star zone arcs and body labels visible | |
| UAT-064 | Light / Dark theme toggle changes SVG colours | System map window open | Click "Light Theme" or "Dark Theme" button | SVG background and element colours update; button label toggles to the opposite theme | |
| UAT-065 | "Save SVG…" saves a valid SVG file | System map window open | Click "Save SVG…"; confirm path | File saved; opening in a browser or SVG viewer displays the map correctly | |
| UAT-066 | Multiple System Map windows can coexist | System result visible | Click "System Map" three times | Three separate map windows open simultaneously; each displays the same map independently | |

---

## 11. View menu / Dark Mode

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-067 | View > Dark Mode toggles application theme | App running (any state) | Click View > Dark Mode | App stylesheet switches to dark palette (dark background, light text); menu action gains a checkmark | |
| UAT-068 | Dark Mode re-renders displayed result with dark theme | World or system result visible | Toggle View > Dark Mode | HTML card in result panel updates to dark background without re-generating; HTML tab CSS variables reflect the theme | |
| UAT-069 | Dark Mode preference persists across app restart | Dark Mode enabled | Quit and relaunch app | App starts in dark mode; View > Dark Mode is checked | |

---

## 12. Survey Form

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-070 | "Survey Form" button and combo visible after system generation | "System detail" checked; system generated | Observe result header | "Survey Form" button present; immediately to its right a dropdown showing "Class 0/I Survey" | |
| UAT-071 | "Survey Form" button absent in world-only mode | "System detail" unchecked | Generate a world | No "Survey Form" button visible in result header | |
| UAT-072 | Clicking "Survey Form" opens a SurveyFormWindow | System generated | Select "Class 0/I Survey" in combo; click "Survey Form" | New window opens titled "Class 0/I Survey — \<designation\>"; IISS Class 0/I form displayed | |
| UAT-073 | Survey form shows stellar component table with correct data | SurveyFormWindow open | Observe stellar table | Rows for each star: component designation, spectral class, mass, temp, diameter, luminosity, orbit number, AU, eccentricity, orbital period in years, HZCO | |
| UAT-074 | Survey form Notes field lists sub-year periods in standard days | SurveyFormWindow open for a system with close companions | Observe Notes field | Notes lists each companion star whose period is under 1 year, converted to standard days with a superscript footnote (e.g. `¹ Ab: 45.312 standard days`) | |
| UAT-075 | Survey form follows current Dark Mode setting | Dark Mode active | Generate system; click "Survey Form" | Form opens with dark background and light text matching the app Dark Mode | |
| UAT-076 | Multiple Survey Form windows can coexist | System result visible | Click "Survey Form" three times | Three separate form windows open; each displays the same survey data independently | |

---

## 13. Keyboard shortcuts

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-077 | Quit shortcut closes the application | App running | Press Cmd+Q (macOS) or Ctrl+Q (Windows/Linux) | Application closes cleanly | |
| UAT-078 | Close shortcut closes the active window | System Map or Survey Form window open and focused | Press Cmd+W (macOS) or Ctrl+W (Windows/Linux) | Active window closes; other windows remain open | |

---

## 14. State transitions

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-079 | Switching source radio clears result | World result visible from Procedural | Click "TravellerMap" radio | Result panel clears or resets to placeholder; TM controls shown | |
| UAT-080 | Switching back to Procedural restores procedural controls | TravellerMap source selected | Click "Procedural" radio | Name and seed fields visible; TM-specific fields hidden | |
| UAT-081 | Seed shown after generation matches seed used | Procedural source; seed field empty | Click "Generate" | Seed field shows the integer seed that was used; generating again with that value produces the same world (see UAT-005) | |
| UAT-082 | Re-generating without changing options produces different world | Procedural source; "System detail" unchecked | Generate; note UWP; click "Generate" again without entering a seed | New seed auto-assigned; world UWP differs from previous result | |
