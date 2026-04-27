# Traveller World Generator — GTK4 UI

A desktop GUI for the Traveller World Generator, built with GTK4 and PyGObject.
Generates mainworlds (procedural or from TravellerMap) and displays the result
as a native GTK4 widget card inside the application window.

---

## Status

Procedural mainworld generation, TravellerMap mainworld lookup, and full system
generation are all working and displayed in-app using native GTK4 widgets.
The Attach detail checkbox is present in the UI but not yet wired.

---

## Requirements

PyGObject is not available via pip on macOS. Install GTK4 and its Python
bindings via Homebrew:

```bash
brew install pygobject3 gtk4
```

The app must be run with the Homebrew-managed Python interpreter (not the
project's `.venv-1`):

```bash
$(brew --prefix)/bin/python3 gen-ui/app.py
```

Tested with:

| Package | Version |
|---------|---------|
| Python (Homebrew) | 3.14 |
| GTK | 4.x |
| PyGObject | 3.42+ |

---

## Running

From the project root:

```bash
$(brew --prefix)/bin/python3 gen-ui/app.py
```

---

## Usage

### Procedural generation

1. Select **Procedural** (default).
2. Enter an optional world name in the **Name** field (defaults to `Unknown`).
3. Enter an optional integer **Seed** for reproducible results, or click
   **New Seed** to randomise.
4. Optionally check **Full system** to generate stellar and orbit data.
5. Click **Generate** or press Enter.

### TravellerMap lookup

1. Select **TravellerMap**.
2. Enter the **Sector** name (required — many world names appear in multiple
   sectors).
3. Enter the world **Name** to search, or the **Hex** position (e.g. `1910`)
   for a direct lookup. Providing a hex bypasses name search entirely and
   avoids ambiguity.
4. Optionally check **Full system**.
5. Click **Generate** or press Enter.

If the name matches more than one world in the sector a disambiguation dialog
lists all candidates with their hex positions; select one and click **OK**.

The canonical world name from TravellerMap is used in the result regardless of
what was typed in the Name field.

### After generation

The GTK window shows a scrollable world card with:

- **Header bar** — world name, UWP (monospace), travel zone badge
- **Stat boxes** — Starport (quality + facilities), Size (diameter + gravity),
  Tech Level (hex value + era)
- **Physical card** — Atmosphere, Survival gear, Temperature, Hydrographics,
  Gas giants, Planetoid belts, PBG
- **Society card** — Population (with multiplier), Government, Law level, Bases
- **Trade code badges** — full name beside each code
- **Notes** — any generation notes

When **Full system** is checked, the card also includes:

- **Stellar System table** — Designation, Classification, Mass (M☉), Temp (K),
  Luminosity (L☉), Orbit (AU) for every star
- **System Orbits table** — Star, Orbit#, AU, Type, HZ marker, Temp Zone for
  every orbit slot; mainworld row is bold, empty orbits are dimmed

A **Stellar & Orbits** toggle switch in the header hides/shows the stellar and
orbit tables without regenerating.

Use **Open in Browser** to view the full styled HTML card in the default browser.
Use **Save…** with the format dropdown to save as JSON, Text, or HTML.

Each Generate call replaces the previous temp HTML file; old files are not
accumulated.

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Enter (in any field) | Generate |
| Cmd+Q / Ctrl+Q | Quit |
| Cmd+W / Ctrl+W | Close window |

> **macOS note:** GTK4's Quartz backend maps `<primary>` to Control, not
> Command. Both `<meta>` (Command) and `<primary>` (Control) are registered,
> so both variants work.

---

## HTML output

The HTML card is produced by `World.to_html()` (mainworld only) or
`TravellerSystem.to_html(detail_attached=False)` (full system) in the
respective generation modules. It is a self-contained page with embedded CSS,
dark mode support, and all world characteristics laid out as a formatted card.

### Why native widgets instead of in-app HTML?

WebKitGTK (the GTK4 HTML renderer) requires Linux. Its dependencies —
`systemd`, `wayland`, `wpebackend-fdo` — are not available on macOS, so
`brew install webkitgtk` fails. The in-app card is therefore built from native
GTK4 widgets (`Gtk.Frame`, `Gtk.Grid`, `Gtk.FlowBox`, `Gtk.ScrolledWindow`).
The HTML representation is still available via **Open in Browser** and **Save…**.

On Linux, WebKitGTK can be installed and the app could be updated to embed the
HTML card directly:

```bash
sudo apt install gir1.2-webkit-6.0   # Debian/Ubuntu
```

See `requirements.txt` for details.

---

## Files

| File | Description |
|------|-------------|
| `app.py` | GTK4 application — `App`, `AppWindow` classes |
| `requirements.txt` | Dependency notes and HTML rendering constraints |

---

## Architecture

The UI is a standard GTK4 `Gtk.Application` / `Gtk.ApplicationWindow`. Three
control rows sit at the top of the window:

1. **Controls row** — Name, Seed, New Seed button, Generate button
2. **Source row** — Procedural / TravellerMap radio buttons; Sector, Name, and
   Hex fields (Sector/Name/Hex are insensitive when Procedural is active)
3. **Options row** — Full system / Attach detail checkboxes; Format dropdown
   (Attach detail not yet wired)

The status panel below the separator fills the remaining window height and
updates after each generation.

### Mainworld-only path

`_finish_generation(world)` calls `_show_summary(world)`, which builds:
- `_build_summary_header(world)` — fixed header bar with name/UWP/zone and
  action buttons
- `_build_world_card(world)` inside a `Gtk.ScrolledWindow`

`_build_world_card` composes: `_build_stat_row`, `_build_detail_cards`,
`_build_trade_codes`, `_build_notes`.

### Full system path

`_finish_system_generation(system)` calls `_show_system_summary(system)`, which
builds:
- `_build_system_summary_header(system)` — returns `(header_bar, orbit_switch)`;
  header shows world name/UWP/zone, Stellar & Orbits toggle switch, and action
  buttons
- `_build_stellar_card(system)` — `Gtk.Frame` + `Gtk.Grid` stars table
- `_build_orbits_card(system)` — `Gtk.Frame` + `Gtk.Grid` orbits table
- Optional mainworld `Gtk.Frame` wrapping `_build_world_card(world)`, all inside
  a `Gtk.ScrolledWindow`

The `notify::active` signal on the switch calls `set_visible()` on both the
stellar and orbits cards.

### TravellerMap path

`generate_system_from_map()` in `traveller_map_fetch.py` is called directly.
When a name search returns multiple exact matches in the same sector,
`AmbiguousWorldError` is raised and caught in `_do_travellermap_generation()`,
which opens a modal disambiguation dialog. Selecting a candidate retries with
its hex position, bypassing name resolution.

---

## Licence

MIT — see the `LICENSE` file in the project root.

The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977–2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
