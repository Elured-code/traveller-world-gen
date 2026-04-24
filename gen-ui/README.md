# Traveller System Generator — GTK4 UI

A desktop GUI for the Traveller World & System Generator, built with GTK4 and
PyGObject.

---

## Status

Early skeleton. Presents a blank 900×600 application window. Generation logic
is not yet wired up.

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

## Files

| File | Description |
|------|-------------|
| `app.py` | GTK4 application entry point — `App` / `AppWindow` classes |
| `requirements.txt` | Dependency notes (Homebrew install instructions) |

---

## Architecture

The UI is a standard GTK4 application using `Gtk.Application` and
`Gtk.ApplicationWindow`. The `do_activate()` method follows the GTK pattern of
reusing an existing window rather than creating a new one on each activation.

The generation backend lives in the parent directory and is imported directly —
no subprocess or HTTP calls are needed for local use.

---

## Licence

MIT — see the `LICENSE` file in the project root.

The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977–2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
