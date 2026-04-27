# Traveller World Generator — GTK4 UI

A desktop GUI for the Traveller World Generator, built with GTK4 and PyGObject.
Generates mainworlds (procedural or from TravellerMap) and displays the result
as a styled HTML card in the system default browser.

---

## Status

Procedural mainworld generation and TravellerMap mainworld lookup are both
working. System generation controls (full system, attach detail, output format)
are present in the UI but not yet wired to generation logic.

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
4. Click **Generate** or press Enter.

### TravellerMap lookup

1. Select **TravellerMap**.
2. Enter the **Sector** name (required — many world names appear in multiple
   sectors).
3. Enter the world **Name** to search, or the **Hex** position (e.g. `1910`)
   for a direct lookup. Providing a hex bypasses name search entirely and
   avoids ambiguity.
4. Click **Generate** or press Enter.

If the name matches more than one world in the sector a disambiguation dialog
lists all candidates with their hex positions; select one and click **OK**.

The canonical world name from TravellerMap is used in the result regardless of
what was typed in the Name field.

### After generation

The GTK window shows a compact summary — world name, UWP, travel zone badge,
trade codes, and bases. The full styled HTML card opens automatically in the
default browser. Use **Reopen HTML Card** to bring it back if the tab is closed.

Each Generate call replaces the previous temp file; old files are not
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

The HTML card is produced by `World.to_html()` in `traveller_world_gen.py`. It
is a self-contained page with embedded CSS, dark mode support, and all world
characteristics laid out as a formatted card.

### Why the browser, not in-app?

WebKitGTK (the GTK4 HTML renderer) requires Linux. Its dependencies —
`systemd`, `wayland`, `wpebackend-fdo` — are not available on macOS, so
`brew install webkitgtk` fails. The HTML is therefore opened via
`Gio.AppInfo.launch_default_for_uri` in the system default browser.

On Linux, WebKitGTK can be installed and the app could be updated to embed the
card directly:

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
   (not yet wired)

The status panel below updates after each generation with a compact world
summary, Reopen and Save actions.

### TravellerMap path

`generate_system_from_map()` in `traveller_map_fetch.py` is called directly.
When a name search returns multiple exact matches in the same sector,
`AmbiguousWorldError` is raised and caught in `_do_travellermap_generation()`,
which opens a modal disambiguation dialog. Selecting a candidate retries with
its hex position, bypassing name resolution.

### Procedural path

`generate_world()` in `traveller_world_gen.py` is imported directly — no
subprocess or HTTP calls are needed.

---

## Licence

MIT — see the `LICENSE` file in the project root.

The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977–2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
