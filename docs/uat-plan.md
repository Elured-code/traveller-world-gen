# gen-ui User Acceptance Test Plan

**Application:** `gen-ui/app.py` — PySide6 desktop UI for the Traveller World & System Generator  
**Last updated:** 2026-05-12 (Session 32)  
**Test type:** Manual (no automated runner)

---

## Scope

Covers all interactive features of the `AppWindow` and `SystemMapWindow` classes as
of Session 32.  Backend generation logic is covered by the automated pytest suite;
this plan focuses on observable UI behaviour only.

## Environment

| Requirement | Detail |
|-------------|--------|
| Python | 3.11 via `.venv` |
| Launch | `.venv/bin/python gen-ui/app.py` from the repo root |
| macOS SSL | Run `Install Certificates.command` in the Python framework dir before testing TravellerMap lookups |
| Network | Tests in §5 (TravellerMap) require an active internet connection |

## How to record results

Fill in the **Result** column with **Pass**, **Fail**, or **Skip** (with a brief
note when failing or skipping).  Re-run failed cases after any fix and record the
re-run outcome alongside the original.

---

## 1. Startup

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-001 | Application launches without error | `.venv` active | Run `.venv/bin/python gen-ui/app.py` | Main window opens; no console traceback | |
| UAT-002 | Initial widget state | App just launched | Observe controls panel | "Procedural" radio selected; "TravellerMap" radio present; "System detail" checkbox unchecked and enabled; "Mainworld detail" checkbox unchecked and **disabled**; "Generate" button present | |
| UAT-003 | Initial result panel shows placeholder | App just launched | Observe result area | Result panel is empty / shows a placeholder; no world card or error visible | |

---

## 2. Controls and seed handling

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-004 | Auto-seed generated when seed field is empty | Procedural source; seed field empty | Click "Generate" | Seed field is populated with a numeric value after generation | |
| UAT-005 | Manual seed is used when entered | Procedural source | Enter `12345` in seed field; click "Generate" twice | Both runs produce identical world name, UWP, and stats | |
| UAT-006 | "New Seed" button clears the seed | Seed field contains a value | Click "New Seed" | Seed field becomes empty (or auto-resets); next generate uses a fresh seed | |
| UAT-007 | Non-integer seed shows error | Procedural source | Enter `abc` in seed field; click "Generate" | Error message "Seed must be an integer." displayed; no world generated | |
| UAT-008 | Return key in name field triggers generate | Procedural source; name field focused | Type a name; press Return | Generation runs as if "Generate" was clicked | |
| UAT-009 | Return key in seed field triggers generate | Procedural source; seed field focused | Type a valid integer; press Return | Generation runs as if "Generate" was clicked | |

---

## 3. Procedural world generation (world-only mode)

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-010 | World generated with custom name | Procedural; "System detail" unchecked | Enter "Cogri" in name field; click "Generate" | World card displayed with name "Cogri" in header | |
| UAT-011 | World generated with empty name uses "Unknown" | Procedural; "System detail" unchecked; name field empty | Click "Generate" | World card header shows "Unknown" | |
| UAT-012 | Same seed reproduces identical world | Procedural; "System detail" unchecked | Generate with seed `99`; note UWP; click "New Seed"; enter `99` again; generate | UWP and all stats identical to first run | |
| UAT-013 | World card shows UWP in monospace | Any world result | Observe world card header | UWP string (e.g. `A867A69-F`) displayed in monospace font alongside world name | |
| UAT-014 | World-only result has no "System Map" button | Procedural; "System detail" unchecked | Generate a world | No "System Map" button visible in result header | |

---

## 4. Procedural system generation

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-015 | "System detail" checkbox enables "Mainworld detail" | App launched; both unchecked | Check "System detail" | "Mainworld detail" checkbox becomes enabled | |
| UAT-016 | Unchecking "System detail" disables and unchecks "Mainworld detail" | "System detail" and "Mainworld detail" both checked | Uncheck "System detail" | "Mainworld detail" becomes unchecked and disabled | |
| UAT-017 | Full system generation produces stellar and orbit cards | "System detail" checked | Click "Generate" | Result shows Stellar System card and System Orbits card in addition to Mainworld panel | |
| UAT-018 | "Mainworld detail" generates World Body card | "System detail" and "Mainworld detail" both checked | Click "Generate" | Mainworld panel contains a "World Body" card (or "Belt Body" for asteroid mainworld) with composition, diameter, gravity etc. | |
| UAT-019 | "Mainworld detail" also generates Atmosphere Detail card | "System detail" and "Mainworld detail" both checked | Click "Generate" | Mainworld panel contains an "Atmosphere Detail" card with Profile, Pressure, and/or O₂ partial pressure rows | |
| UAT-020 | "System Map" button enabled only when "System detail" is checked | System result visible | Uncheck "System detail"; re-generate | "System Map" button is disabled; re-check "System detail" and generate again — button is enabled | |

---

## 5. TravellerMap lookup

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-021 | Switching to TravellerMap source shows TM controls | Procedural selected | Click "TravellerMap" radio | TM-specific controls (Sector, World name, Hex fields) appear; procedural name/seed controls hidden | |
| UAT-022 | Name search returns world result | TravellerMap source; internet available | Enter sector "Spinward Marches", name "Regina"; click "Generate" | World card displayed for Regina with correct UWP | |
| UAT-023 | Hex search returns world result | TravellerMap source; internet available | Enter sector "Spinward Marches", hex "1910"; click "Generate" | World card displayed for the world at hex 1910 | |
| UAT-024 | Generate without sector shows error | TravellerMap source; sector field empty | Click "Generate" | Error message "Sector is required for TravellerMap lookup." | |
| UAT-025 | Generate without name or hex shows error | TravellerMap source; sector entered; name and hex fields empty | Click "Generate" | Error message "Enter a world name or hex for TravellerMap lookup." | |
| UAT-026 | Ambiguous world name shows disambiguation dialog | TravellerMap source; internet available | Enter a sector and a name that matches multiple worlds | Disambiguation dialog appears listing candidate worlds; selecting one proceeds to generation | |
| UAT-027 | TravellerMap result shows canonical UWP in orbit table | TravellerMap source; "System detail" checked; internet available | Fetch a known world | Mainworld orbit slot in the orbit table shows the canonical UWP from TravellerMap, not a procedurally generated one | |

---

## 6. World card display

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-028 | Stat row shows Starport, Size, Tech Level boxes | Any world result | Observe top of world card | Three stat boxes visible: Starport (code + quality label), Size (code + diameter), Tech Level (code + era badge) | |
| UAT-029 | Physical inner card shows atmosphere, temperature, hydrographics | Any world result | Observe "Physical" inner card | Rows for Atmosphere, Survival gear, Temperature, Hydrographics, Gas giants, Planetoid belts, PBG | |
| UAT-030 | Society inner card shows population, government, law, bases | Any world result | Observe "Society" inner card | Rows for Population, Government, Law level, Bases | |
| UAT-031 | Trade codes displayed as badges | World with trade codes | Observe trade code row | Each trade code shown as a coloured badge with full name (e.g. "Ag — Agricultural") | |
| UAT-032 | Notes section appears for worlds with generation warnings | Generate worlds until a note appears (or use a known seed) | Observe notes card | Notes group box present, each note listed with a bullet | |
| UAT-033 | Atmosphere Detail card shows profile and quantitative values | "Mainworld detail" checked; generate a system | Observe "Atmosphere Detail" card | Card present with Profile string (e.g. `6-1.013-0.212`), Pressure, and/or O₂ partial pressure, Scale height rows | |
| UAT-034 | Atmosphere Detail card shows taint details | Generate until a tainted atmosphere (codes 2/4/7/9) appears | Observe "Atmosphere Detail" card | Taint rows present: subtype name, Severity description, Persistence description | |
| UAT-035 | Two taints show numbered labels | Generate until cascade taint occurs (rare; or use a known seed) | Observe taint rows | Labels read "Taint 1" and "Taint 2" rather than plain "Taint" | |

---

## 7. System view display

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-036 | Stellar card shows system age and star entries | "System detail" checked; system generated | Observe "Stellar System" card | System age in Gyr displayed; table rows for each star showing designation, spectral type, luminosity class | |
| UAT-037 | Orbit table shows all orbit slots | "System detail" checked | Observe "System Orbits" card | Rows for each orbit slot with star, orbit number, type, and profile columns | |
| UAT-038 | Mainworld orbit slot highlighted or labelled | System with mainworld | Observe orbit table | Mainworld slot identifiable (e.g. labelled or shows canonical UWP) | |
| UAT-039 | "Stellar & Orbits" toggle shows and hides cards | System result visible | Uncheck "Stellar & Orbits" checkbox | Stellar System and System Orbits cards collapse / hide; re-checking restores them | |
| UAT-040 | Mainworld panel present in system result | "System detail" checked | Observe below orbit table | "Mainworld" group box containing the world card is visible | |
| UAT-041 | Gas giant mainworld shows satellite UWP in mainworld panel | Generate until gas giant mainworld (or use a known seed) | Observe mainworld panel | Panel displays the satellite world's UWP and characteristics, not the gas giant's profile | |

---

## 8. Action buttons

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-042 | "Open in Browser" opens HTML in default browser | Any world or system result | Click "Open in Browser" | Default browser opens showing the world/system HTML card | |
| UAT-043 | Save as JSON produces valid file | Any world or system result | Click "Save…"; choose JSON format; confirm path | File saved; opening it shows valid JSON with `name`, `uwp`, and all expected fields | |
| UAT-044 | Save as TXT produces readable summary | Any world result | Click "Save…"; choose TXT format; confirm path | File saved; opening it shows the plain-text summary with UWP, stats, and sections | |
| UAT-045 | Save as HTML produces correct HTML file | Any world result | Click "Save…"; choose HTML format; confirm path | File saved; opening in browser shows the world card matching the in-app display | |
| UAT-046 | Atmosphere detail and size detail appear in saved HTML | "Mainworld detail" checked; system generated | Save as HTML | Saved HTML contains "Atmosphere detail" and "World Body" (or "Belt Body") inner cards | |
| UAT-047 | Generating a new world replaces the result panel | World result visible | Change name; click "Generate" | Previous result replaced by new world card; no duplication or error | |

---

## 9. System Map window

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-048 | "System Map" button opens map window | System result visible; "System detail" checked | Click "System Map" | A new `SystemMapWindow` opens with an SVG star system map rendered | |
| UAT-049 | Map shows all system bodies | System map window open | Observe SVG | Orbits and body types (gas giant, belt, terrestrial, empty) represented; star zone arcs visible | |
| UAT-050 | Light / Dark theme toggle changes SVG colours | System map window open | Click "Light Theme" or "Dark Theme" | SVG background and element colours change; button label updates to the opposite theme | |
| UAT-051 | "Save SVG…" saves a valid SVG file | System map window open | Click "Save SVG…"; confirm path | File saved; opening in a browser or SVG viewer displays the map correctly | |
| UAT-052 | Multiple System Map windows can coexist | System result visible | Click "System Map" three times | Three separate map windows open simultaneously; each displays the same map independently | |

---

## 10. Keyboard shortcuts

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-053 | Quit shortcut closes the application | App running | Press Cmd+Q (macOS) or Ctrl+Q (Windows/Linux) | Application closes cleanly | |
| UAT-054 | Close shortcut closes the active window | System Map window open and focused | Press Cmd+W (macOS) or Ctrl+W (Windows/Linux) | Active window (map or main) closes; other windows remain open | |

---

## 11. State transitions

| ID | Description | Pre-conditions | Steps | Expected result | Result |
|----|-------------|----------------|-------|-----------------|--------|
| UAT-055 | Switching source radio clears result | World result visible from Procedural | Click "TravellerMap" radio | Result panel clears or resets to placeholder; TM controls shown | |
| UAT-056 | Switching back to Procedural restores procedural controls | TravellerMap source selected | Click "Procedural" radio | Name and seed fields visible; TM-specific fields hidden | |
| UAT-057 | Seed shown after generation matches seed used | Procedural source; seed field empty | Click "Generate" | Seed field shows the integer seed that was used; generating again with that value produces the same world (see UAT-005) | |
| UAT-058 | Re-generating without changing options produces different world | Procedural source; "System detail" unchecked | Generate; note UWP; click "Generate" again | New seed auto-assigned; world UWP differs from previous result (statistically certain) | |
