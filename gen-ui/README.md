# Traveller World Generator — GTK4 UI

A desktop GUI for the Traveller World Generator, built with GTK4 and PyGObject.
Generates mainworlds using the CRB rules and displays the result as a styled
HTML card in the system default browser.

---

## Status

Working — mainworld generation with HTML card output.

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

1. Enter an optional world name in the **Name** field (defaults to `Unknown`).
2. Enter an optional integer **Seed** for reproducible results.
3. Click **Generate** or press Enter.

The GTK window shows a compact summary — world name, UWP, travel zone badge,
trade codes, and bases. The full styled HTML card opens automatically in the
default browser. Use **Reopen HTML Card** to bring it back if the tab is closed.

Each Generate call replaces the previous temp file; old files are not
accumulated.

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

The UI is a standard GTK4 `Gtk.Application` / `Gtk.ApplicationWindow`. The
control panel (name, seed, generate button) sits at the top of the window. The
status panel below updates after each generation with a compact world summary.

The generation backend (`traveller_world_gen.py`) is imported directly from the
parent directory — no subprocess or HTTP calls are needed.

---

## Licence

MIT — see the `LICENSE` file in the project root.

The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977–2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
