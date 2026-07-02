# Traveller World Generator — User Guide

## Starting the app

From the project root with the virtual environment active:

```bash
python gen-ui/app.py
```

The window opens with a brief onboarding card describing the three-step workflow.

---

## The main window

The top of the window has two control areas:

**Controls row** — world name, seed, and the Generate button.

**Source row** — selects where world data comes from (Procedural or TravellerMap)
and provides an **Options…** button for generation settings.

Results fill the remainder of the window below a horizontal separator.

---

## Generating a world

### Procedural

1. Make sure **Procedural** is selected (it is by default).
2. Enter a name in the **Name** field, or leave it blank for `Unknown`.
3. Enter an integer in **Seed** for a reproducible result, or leave it blank.
   Click **New Seed** to fill in a random seed without generating.
4. Click **Generate**, or press Enter from any field.

### TravellerMap

Look up a real world from the official Traveller universe via TravellerMap.

1. Select **TravellerMap**. A panel with Sector, Name, and Hex fields appears.
2. Enter the **Sector** name (required). Many world names appear in multiple
   sectors, so the sector is used to narrow the search.
3. Enter either a world **Name** (e.g. `Regina`) or a **Hex** position
   (e.g. `1910`). Providing a hex is unambiguous and skips name resolution.
4. Click **Generate** or press Enter.

If a name search returns more than one match a disambiguation dialog lists all
candidates with their hex positions. Select one and click **OK**.

The seed field still applies in TravellerMap mode — it seeds the procedural
detail generated on top of the retrieved UWP.

---

## Generation options

Click **Options…** to open the generation options dialog. Settings are saved
between sessions.

### System detail

When checked, the generator creates a full star system (stellar data, orbit
layout, and all worlds) rather than a standalone mainworld. The result gains a
**System tab** alongside the Mainworld tab, and the **System Map** button
appears in the result header.

When System detail is on, five sub-options become available:

| Option | What it does |
|--------|-------------|
| **NHZ Atmospheres** | Allows worlds outside the habitable zone to have non-standard atmosphere types that would otherwise only appear in the HZ. |
| **Oxygen requires biomass** | Free oxygen is unstable without life to replenish it. When checked, oxygen-bearing atmospheres require a biosphere to sustain them. |
| **Advanced temperature** | Calculates a physics-based mean surface temperature from luminosity, orbit distance, and atmospheric pressure, replacing the basic temperature band. |
| **Runaway greenhouse** | Applies Venus-like runaway greenhouse conditions to worlds that qualify — raises temperature to Boiling and may alter the atmosphere. |
| **Independent government** | Secondary worlds may develop their own government independent of the mainworld (WBH Case 2, p.162). When off, secondary worlds default to the mainworld's political authority. |

### Population detail

Generates a detailed breakdown of the world's population structure (density,
demographics, settlement pattern). Works in both mainworld-only and full system
modes. Not gated by System detail.

### Government detail

Generates detailed government structure. Uses population data when Population
detail is also enabled. Works in both modes and is not gated by System detail.

### Settlement type

Controls the age and character of the world's settlement history, which
influences population, government, and law level.

| Type | Description |
|------|-------------|
| **Standard** | Default Traveller settlement pattern. |
| **Long-settled** | Old, well-established colony with entrenched social structures. |
| **Well-settled** | Densely populated and fully integrated into the Imperium. |
| **Backwater** | Frontier world, under-developed, low traffic. |
| **Unsettled** | No permanent population or very recently established. |

Settlement type is not applied to TravellerMap lookups, which use the UWP
retrieved from TravellerMap directly.

---

## Reading the results

### Mainworld-only result

The header bar shows the world name, UWP in monospace, and a colour-coded
travel zone badge (green / amber / red).

The scrollable world card below the header displays:

- **Stat boxes** — Starport (class and facilities), Size (diameter and gravity),
  Tech Level (hex digit and era name)
- **Physical characteristics** — Atmosphere type and breathability, survival
  gear requirements, Temperature category, Hydrographics, Gas giants and
  planetoid belts, PBG figures
- **Society** — Population with multiplier, Government type, Law level, Bases
- **Trade codes** — badges with full trade code names
- **Notes** — any notable generation flags

### Full system result

Two tabs appear below the header:

**System tab** — a scrollable HTML table showing every orbit around every star:
star designation, orbit number, distance in AU, eccentricity/inclination, world
type, UWP or gas giant SAH, trade codes, HZ marker, temperature zone, orbital
period, and notes. The mainworld row is bold. When System detail is on, moon
sub-rows are indented under their parent orbit.

**Mainworld tab** — the same detailed world card as the mainworld-only result.
This tab is selected by default when a mainworld exists.

The header also shows a **System Map** button (see below).

---

## System Map

Click **System Map** in the result header to open a visual map of the star
system. Multiple map windows can be open at once — each Generate call produces
its own independent map.

The map toolbar has three controls:

| Control | Effect |
|---------|--------|
| **Light Theme / Dark Theme** | Toggles the map colour palette. |
| **Perspective View / Top-down View** | Switches between a tilted 3-D perspective and a flat overhead view. |
| **Save SVG…** | Saves the current map as an SVG file. |

---

## Dark mode

**View > Dark Mode** toggles the application theme. The setting is saved between
sessions. The world card and system HTML views update immediately when the theme
is changed without regenerating.

---

## Saving and loading

### Save As… (Ctrl+S / Cmd+S)

Available after any generation. Opens a file dialog offering two formats:

- **HTML** — a self-contained page with embedded CSS and dark-mode support,
  suitable for sharing or archiving.
- **JSON** — machine-readable world or system data that can be reloaded into
  the app.

System results saved as JSON include all orbit and stellar data. The file is
tagged with the app version so that version mismatches can be detected on reload.

### Open JSON… (File menu)

Loads a previously saved JSON file. If the file was saved with a different
version of the app a warning dialog gives the option to continue loading or
abort. System JSONs (containing a `"stars"` key) are fully reconstructed
including secondary world detail.

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Enter (in any field) | Generate |
| Ctrl+S / Cmd+S | Save As… |
| Ctrl+Q / Cmd+Q | Quit |
| Ctrl+W / Cmd+W | Close window |
