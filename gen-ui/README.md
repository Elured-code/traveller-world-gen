# Traveller World Generator — Qt UI

A desktop GUI for the Traveller World Generator, built with PySide6 (Qt6).
Generates mainworlds (procedural or from TravellerMap) and displays the result
as a native Qt widget card inside the application window. Runs on macOS,
Windows, and Linux from the same pip-installed package.

---

## Status

Procedural mainworld generation, TravellerMap mainworld lookup, full system
generation, and attach detail are all working and displayed in-app using native
Qt widgets.

---

## Requirements

PySide6 bundles Qt — no system packages (Homebrew, apt, etc.) required.
Install into the project venv:

```bash
.venv-1/bin/pip install "PySide6>=6.4.0"
```

Tested with:

| Package | Version |
|---------|---------|
| Python (.venv-1) | 3.11 |
| PySide6 | 6.4+ |

---

## Running

From the project root with the venv active:

```bash
source .venv-1/bin/activate
python gen-ui/app.py
```

Or without activating the venv:

```bash
.venv-1/bin/python3 gen-ui/app.py
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

The window shows a scrollable world card with:

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

A **Stellar & Orbits** checkbox in the header hides/shows the stellar and
orbit tables without regenerating.

When **Full system** and **Attach detail** are both checked, the System Orbits
table gains extra columns and moon sub-rows:

- **Additional columns** — Profile (UWP or gas giant SAH), Trade codes
- **Moon sub-rows** — indented below each orbit slot; show type, profile (ring
  count as `R{n}`, or UWP if detailed, or size code), and any trade codes
- **Mainworld** is treated as a satellite when its orbit is a gas giant, and a
  note is shown in the world card recording the host giant and orbit

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

Qt maps `QKeySequence::Quit` and `QKeySequence::Close` to the correct
platform-native keys automatically.

---

## HTML output

The HTML card is produced by `World.to_html()` (mainworld only) or
`TravellerSystem.to_html(detail_attached=False)` (full system) in the
respective generation modules. It is a self-contained page with embedded CSS,
dark mode support, and all world characteristics laid out as a formatted card.

### Why native widgets instead of in-app HTML?

The in-app card uses native Qt widgets for simplicity and cross-platform
consistency. PySide6 includes `QtWebEngineWidgets` (a Chromium-based renderer)
which could be used to embed the HTML card directly if desired:

```python
from PySide6.QtWebEngineWidgets import QWebEngineView
view = QWebEngineView()
view.setHtml(html)
```

This is a deferred feature — see `requirements.txt`.

---

## Files

| File | Description |
|------|-------------|
| `app.py` | Qt application — `AppWindow(QMainWindow)` |
| `requirements.txt` | Dependency notes |

---

## Architecture

The UI is a `QMainWindow` with a central `QWidget` and a root `QVBoxLayout`.
Three control rows sit at the top of the window:

1. **Controls row** — Name, Seed, New Seed button, Generate button
2. **Source row** — Procedural / TravellerMap radio buttons; Sector, Name, and
   Hex fields (disabled when Procedural is active)
3. **Options row** — Full system / Attach detail checkboxes
   (Attach detail is only enabled when Full system is checked)

The status panel (`_status_widget` / `_status_layout`) below the separator
fills the remaining window height and is cleared and rebuilt on each generation.

### Mainworld-only path

`_finish_generation(world)` calls `_show_summary(world)`, which builds:
- `_build_summary_header(world)` — fixed header bar with name/UWP/zone and
  action buttons
- `_build_world_card(world)` inside a `QScrollArea`

`_build_world_card` composes: `_build_stat_row`, `_build_detail_cards`,
`_build_trade_codes`, `_build_notes`.

### Full system path

`_finish_system_generation(system, attach_detail_flag)` optionally calls
`attach_detail(system)` when the Attach detail checkbox is active, sets
`self._detail_attached`, then calls `_show_system_summary(system)`, which builds:
- `_build_system_summary_header(system)` — returns `(header_bar, orbit_toggle)`;
  header shows world name/UWP/zone, Stellar & Orbits checkbox, and action buttons
- `_build_stellar_card(system)` — `QGroupBox` + `QGridLayout` stars table
- `_build_orbits_card(system, detail_attached)` — `QGroupBox` + `QGridLayout`
  orbits table; when `detail_attached=True`, adds Profile and Codes columns and
  inserts moon sub-rows using a free-running `grid_row` counter
- Optional mainworld `QGroupBox` wrapping `_build_world_card(world)`, all inside
  a `QScrollArea`

The `orbit_toggle.toggled` signal calls `setVisible()` on both the stellar and
orbits cards. `self._detail_attached` is used by `_on_save_clicked()` to pass
the correct `detail_attached` flag to `to_html()`.

### TravellerMap path

`generate_system_from_map()` in `traveller_map_fetch.py` is called directly.
When a name search returns multiple exact matches in the same sector,
`AmbiguousWorldError` is raised and caught in `_do_travellermap_generation()`,
which opens a modal `QDialog`. Selecting a candidate retries with its hex
position, bypassing name resolution.

---

## Licence

MIT — see the `LICENSE` file in the project root.

The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977–2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
