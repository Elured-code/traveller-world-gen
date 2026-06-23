# gen-ui User Acceptance Test Plan

**Application:** `gen-ui/app.py` — PySide6 desktop UI for the Traveller World & System Generator  
**Last updated:** 2026-06-23 (Session 138)  
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
| UAT-100 | Aegir (Solomani Rim 1339) UWP preserved after full pipeline | TravellerMap source; "System detail" + "Social detail" both checked; internet available | Enter sector "Solomani Rim", name "Aegir"; click "Generate" | World card shows UWP **A76A885-D** exactly; starport A, pop 8, gov 8, law 5, TL 13 — none overwritten by procedural dice | |
| UAT-101 | Aegir UWP deterministic across multiple seeds | TravellerMap source; "System detail" checked; internet available | Fetch Aegir; note UWP; change seed; fetch again | UWP **A76A885-D** displayed identically on every fetch regardless of seed | |

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

---

## 15. Social detail and cultural profile

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-083 | "Social detail" checkbox present in Options dialog | App running | Open Options | "Social detail" checkbox visible | |
| UAT-084 | Culture section absent when "Social detail" unchecked | "System detail" checked; "Social detail" unchecked | Generate with default options; observe Mainworld tab | World card has no "Culture detail" section | |
| UAT-085 | Culture section present when "Social detail" checked | "System detail" and "Social detail" both checked; world is inhabited (Population > 0) | Generate; observe Mainworld tab | World card shows "Culture detail" header, "Cultural profile" row (e.g. `7567-8432`), and rows for all 8 traits (Diversity, Xenophilia, Uniqueness, Symbology, Cohesion, Progressiveness, Expansionism, Militancy) each with a value and label | |
| UAT-086 | Cultural profile string is DXUS-CPEM format | Social detail enabled; inhabited mainworld generated | Observe "Cultural profile" row in world card | Profile is exactly 9 characters: four eHex digits, a hyphen, four eHex digits (e.g. `85C9-A7B8`) | |
| UAT-087 | All eight trait values are at least 1 | Social detail enabled; inhabited mainworld generated | Observe the 8 trait rows in the Culture section | Each numeric value shown is ≥ 1 | |
| UAT-088 | Inhabited secondary worlds also receive culture detail | "Social detail" checked; system has an inhabited secondary world | Generate system; observe secondary world card | Secondary world card also shows a "Culture detail" section with 8 traits and profile | |
| UAT-089 | World importance row present when "Social detail" checked | "System detail" and "Social detail" both checked; world is inhabited | Generate; scroll to bottom of world card | "World importance" row visible at the bottom of the "Culture detail" section showing a signed integer (e.g. `+2`, `0`, `−1`) | |
| UAT-090 | World importance row absent when "Social detail" unchecked | "System detail" checked; "Social detail" unchecked | Generate; inspect world card | No "World importance" row visible anywhere on the card | |
| UAT-091 | World importance > +3 displayed in bold | Social detail enabled; generate worlds until one has importance > +3 (try Starport A/B, Pop 9+, TL 10+, In or Ri trade codes) | Observe "World importance" row | Value text is visibly bolder than adjacent rows (font-weight 700 vs 500) | |
| UAT-092 | World importance JSON includes all 8 DM components | Social detail enabled; inhabited mainworld generated | Inspect raw JSON (expand "Raw JSON" section in world card or call `/api/system?social_detail=true`) | `importance_detail` object present with keys: `importance`, `starport_dm`, `population_dm`, `tech_dm`, `agricultural_dm`, `industrial_dm`, `rich_dm`, `base_dm`, `waystation_dm` | |
| UAT-093 | Labour factor row visible on social card | Social detail enabled; inhabited world with pop ≥ 2 | Generate; check culture detail section | "Labour factor" row present showing population code − 1 (e.g. pop 7 → labour factor 6) | |
| UAT-094 | Labour factor is 0 for pop 0 or 1 | Social detail enabled; world with pop 0 or 1 | Generate; inspect JSON | `labour_factor` is 0; or `importance_detail` absent for pop 0 | |
| UAT-095 | Infrastructure factor row present for viable worlds | Social detail enabled; inhabited world with positive importance likely (Starport A/B, pop 7+, TL 10+) | Generate; check culture detail section | "Infrastructure factor" row shows an integer ≥ 0 | |
| UAT-096 | Infrastructure factor shows "—" for backwater worlds | Social detail enabled; generate a very backwater world (Starport X, pop 3, TL 4) | Generate; check culture detail section | "Infrastructure factor" row shows "—" | |
| UAT-097 | Resource factor visible on both physical and social card sections | Social detail and system detail both enabled; inhabited world with size_detail | Generate | "Resource factor" row appears once in physical section and once in culture/social section | |
| UAT-098 | Efficiency factor row present on social card | Social detail enabled; inhabited world | Generate | "Efficiency factor" row shows a non-zero integer between −5 and +5 | |
| UAT-099 | Resource units row present on social card | Social detail + system detail enabled; inhabited world | Generate | "Resource units" row shows an integer; negative value shown in red when EF is negative | |
| UAT-100 | GWP per capita and total GWP rows present | Social detail + system detail enabled; inhabited world | Generate | "GWP per capita" row shows Cr-prefixed comma-formatted integer; "Total GWP" shows MCr value | |
| UAT-101 | Development score row present | Social detail + system detail enabled; inhabited world | Generate | "Development score" row shows a decimal value (e.g. "12.50") | |
| UAT-102 | Economics profile row present and bold | Social detail + system detail enabled; inhabited world | Generate | "Economics profile" row shows a 5-character string like "765+2" in bold; EF part has sign | |
| UAT-103 | Economics profile encodes correct values | Social detail + system detail enabled; any inhabited world | Generate; note RF, LF, IF, EF from other rows | First char = RF in eHex, second = LF in eHex, third = IF in eHex (or '0' if absent), remainder = signed EF | |
| UAT-104 | Negative resource units shown in danger style | Social detail + system detail enabled; generate until EF is negative (backwater world, Starport X, pop 3, TL 4, Moribund/Insular culture) | Generate | "Resource units" value displayed in red/danger colour | |

---

## 16. Starport detail (WBH §8, issue #101, Session 137)

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-105 | Starport detail card present when "Social detail" checked | "System detail" + "Social detail" checked; inhabited world with starport A–E | Generate | Mainworld card shows a "Starport" inner card below the Military card | |
| UAT-106 | Starport detail card absent when "Social detail" unchecked | "System detail" checked; "Social detail" unchecked | Generate inhabited world | No "Starport" inner card in world card | |
| UAT-107 | Starport class displayed | Social detail enabled; any inhabited world | Generate; observe Starport card | "Class" row shows the single-letter starport code (e.g. "A") | |
| UAT-108 | Highport indicator correct | Social detail enabled; world with 'H' in bases | Generate; observe Starport card | "Highport" row shows "Yes"; worlds without 'H' in bases show "No" | |
| UAT-109 | Expected weekly traffic shown | Social detail enabled; inhabited world | Generate; observe Starport card | "Expected weekly traffic" row shows a positive integer | |
| UAT-110 | Docking capacity shown | Social detail enabled; inhabited world | Generate; observe Starport card | "Docking capacity" row shows a tonnage value (positive integer) | |
| UAT-111 | Shipyard capacity present for Class A/B | Social detail enabled; world with starport A or B | Generate; observe Starport card | "Shipyard capacity" row shows a positive integer | |
| UAT-112 | Shipyard capacity absent for Class C and below | Social detail enabled; world with starport C, D, or E | Generate; observe Starport card | "Shipyard capacity" row shows "—" or is absent | |
| UAT-113 | Starport profile string shown | Social detail enabled; inhabited world | Generate; observe Starport card | "Profile" row shows a string in WBH format (e.g. `A-HY:DY:+3`) | |
| UAT-114 | Tech level floor enforced for Class A starport | Social detail enabled; generate worlds with Class A starport | Note TL on multiple Class A worlds | Tech level is always ≥ 9 for Class A starport worlds | |
| UAT-115 | Tech level floor enforced for Class B starport | Social detail enabled; generate worlds with Class B starport | Note TL on multiple Class B worlds | Tech level is always ≥ 8 for Class B starport worlds | |

---

## 17. Military detail (WBH §9, issue #102, Session 138)

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-116 | Military detail card present when "Social detail" checked | "System detail" + "Social detail" checked; inhabited world (population ≥ 1) | Generate | Mainworld card shows a "Military" inner card | |
| UAT-117 | Military detail card absent when "Social detail" unchecked | "System detail" checked; "Social detail" unchecked | Generate | No "Military" card in world card | |
| UAT-118 | Military profile string displayed and highlighted | Social detail enabled; inhabited world | Generate; observe Military card | "Profile" row shows a string in EMAWF-SNM:X.XX% format, displayed as a highlighted badge | |
| UAT-119 | State of readiness row shown | Social detail enabled; inhabited world | Generate; observe Military card | "State of readiness" row shows one of: Complacent peace / Low threat level / Normal readiness / Heightened tensions… / War or internal insurgency / Total war: full mobilisation | |
| UAT-120 | Military budget % displayed | Social detail enabled; inhabited world | Generate; observe Military card | "Effective budget %" row shows a decimal percentage | |
| UAT-121 | Military budget MCr displayed | Social detail enabled; inhabited world | Generate; observe Military card | "Military budget" row shows a MCr value | |
| UAT-122 | Enforcement branch always present | Social detail enabled; any inhabited world | Generate; observe Military card | Enforcement branch row always shows an effect value (never "—") | |
| UAT-123 | Absent branches show "—" | Social detail enabled; any inhabited world | Generate; observe Military card | Branches that do not exist (e.g. Navy on low-TL worlds) show "—" for their effect | |
| UAT-124 | Navy absent for TL < 8 | Social detail enabled; generate a world with TL 7 or lower | Generate; observe Military card Navy row | Navy branch shows "—" (does not exist below TL 8) | |
| UAT-125 | Military budget reflects state of readiness | Social detail enabled; generate multiple worlds until one is "Total war: full mobilisation" | Compare budget % between a Complacent peace and Total war world | Total war budget % is significantly higher than Complacent peace | |
| UAT-126 | Military detail absent for uninhabited worlds | Social detail enabled; generate until a population-0 world appears | Observe Mainworld tab | No "Military" card displayed | |

---

## 18. Extended travel zone (WBH §10, issue #103, Session 138)

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-127 | Travel zone row visible on world card | Any world generated | Observe world card header or society card | "Travel zone" row or badge shows "Green", "Amber", or "Red" | |
| UAT-128 | Starport X always Red zone | Social detail enabled; generate until a world with starport X appears | Observe travel zone | Travel zone is "Red" for all starport X worlds | |
| UAT-129 | Extended zone may differ from CRB zone | Social detail enabled; generate many worlds using seed sweep | Compare travel zone output with and without social detail | Some worlds change zone (Green → Amber or Amber → Red) when social detail is applied, due to WBH §10 DMs | |
| UAT-130 | Highly militaristic world likely Amber or Red | Social detail enabled; generate worlds with very high Militancy (≥ 12) | Generate 10+ worlds with high militancy; observe travel zones | Most or all show Amber or Red zone, consistent with high Militancy DMs in §10 table | |
| UAT-131 | Xenophobic world likely Amber or Red | Social detail enabled; generate worlds with Xenophilia 1–2 | Generate worlds; observe travel zone | High proportion of Amber or Red zones; extreme xenophobia is a Red DM | |

---

## 19. Help menu and About dialog (issue #159, Session 138)

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-132 | Help menu present in menu bar | App running | Observe menu bar | "Help" menu visible to the right of "View" | |
| UAT-133 | Help menu contains About action | App running | Click "Help" menu | Single entry "About" visible | |
| UAT-134 | About dialog opens | App running | Click Help → About | Modal dialog opens titled "About Traveller World & System Generator" | |
| UAT-135 | About dialog shows app version | About dialog open | Observe dialog text | Current version string (e.g. `1.5.35`) visible in dialog | |
| UAT-136 | About dialog shows WBH credits | About dialog open | Observe dialog text | Authors Geir Lanesskog and Isabella Treccani-Chinelli credited; "World Builders' Handbook" named | |
| UAT-137 | About dialog shows Traveller Inner Circle | About dialog open | Observe dialog text | "Traveller Inner Circle" heading and list of names visible | |
| UAT-138 | About dialog shows MIT License notice | About dialog open | Observe dialog text | "MIT License" text visible with a clickable hyperlink | |
| UAT-139 | About dialog shows Mongoose Publishing disclaimer | About dialog open | Observe dialog text | Disclaimer text mentions Mongoose Publishing and Far Future Enterprises | |
| UAT-140 | About dialog shows repository link | About dialog open | Observe dialog text | GitHub URL (`github.com/Elured-code/traveller-world-gen`) shown as a clickable hyperlink | |
| UAT-141 | About dialog dismissed with OK | About dialog open | Click OK | Dialog closes; main window remains open and unchanged | |
| UAT-142 | About button present on world card (API/browser) | World card HTML rendered (via API or file save) | Open world card HTML in a browser | Semi-transparent "About" button visible at bottom-right of the page | |
| UAT-143 | World card About modal opens in browser | World card open in browser | Click About button | Native `<dialog>` modal opens with credits content | |
| UAT-144 | World card About modal dismissed with OK | World card About modal open | Click OK button inside modal | Modal closes; page remains as-is | |
| UAT-145 | World card About modal respects dark mode | World card viewed in browser with OS dark mode active | Click About button | Modal background and text use dark-mode CSS variables, matching page theme | |
