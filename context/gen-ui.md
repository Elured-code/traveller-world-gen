# gen-ui.md — gen-ui/app.py (PySide6 Qt6 desktop UI)

Read this when working on the desktop UI, widget state management, PySide6
type-checking patterns, or the SystemMapWindow.

---

## Overview

`gen-ui/app.py` is a PySide6 (Qt6) desktop UI for local interactive use.
PySide6 bundles Qt and has no system-package dependencies.

```bash
python gen-ui/app.py
```

Requires `.venv` with `PySide6>=6.4.0` installed. On macOS, SSL certificates
must be installed via `Install Certificates.command` (in the Python framework
directory) for TravellerMap HTTPS lookups to succeed.

---

## `AppWindow` — main window

Key instance state:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `_current_world` | `object \| None` | Last generated `World` |
| `_current_system` | `object \| None` | Last generated `TravellerSystem` |
| `_detail_attached` | `bool` | Whether `attach_detail()` was called on `_current_system` |
| `_html_path` | `str \| None` | Temp file path of last HTML card (for "Open in Browser") |
| `_map_btn` | `QPushButton \| None` | Active "System Map" button; `None` when no system result |
| `_map_windows` | `list[object]` | Open `SystemMapWindow` instances — list keeps them alive against GC |

### Source row checkboxes

Five checkboxes below the Procedural/TravellerMap radio buttons:

| Checkbox | Enabled when | Effect |
|----------|-------------|--------|
| "Full system" | Always | Calls `generate_full_system()` instead of `generate_world()` |
| "Attach detail" | "Full system" checked | Calls `attach_detail()` after system generation |
| "Physical detail" | "Full system" checked | Calls `generate_world_physical(world, age_gyr)` on the mainworld |
| "NHZ Atmospheres" | "Full system" checked | Passes `nhz_atmospheres=True` to `generate_full_system()` |
| "Orbital Eccentricity" | "Full system" checked | Passes `orbital_eccentricity=True` to `generate_full_system()`; populates `OrbitSlot.eccentricity` and shows values in the Ecc/Incl column |
| "Orbital Inclination" | "Full system" checked | Passes `orbital_inclination=True` to `generate_full_system()`; populates `OrbitSlot.inclination` and shows values in the Ecc/Incl column |

**`_on_system_detail_toggled(checked)`** — enables/disables "Attach detail",
"Physical detail", "NHZ Atmospheres", "Orbital Eccentricity", and "Orbital Inclination"
together, and unchecks all five when "Full system" is turned off.
Also calls `_map_btn.setEnabled(checked)` when `_map_btn` is set.

### "System Map" button lifecycle

The "System Map" button lives in `_build_system_summary_header()` (system results
only; not shown in world-only mode). `_clear_status()` nulls `_map_btn` whenever
the result panel is replaced. `_on_full_system_toggled()` calls
`_map_btn.setEnabled(checked)` when the reference is set.

### `_build_physical_card(w)`

Returns a `QGroupBox("World Body")` when `w.physical` is set, `None` otherwise.
Displays all eight `WorldPhysical` fields as `_detail_row` label/value pairs.
Added to `_build_world_card()` below the trade codes section.

### `_build_stellar_card(system)`

Displays `stars[0].age_gyr` as a plain label above the star table. The star grid
has 7 columns: Desig, Type, Mass (M☉), Temp (K), Lum (L☉), Orbit (AU), Period.
Period is right-aligned; primary shows `—`; companions/secondaries show the value
from `Star.orbit_period_yr` formatted by the module-level `_fmt_period()`.

### `_fmt_period(period_yr)` — module-level helper

```python
def _fmt_period(period_yr: float) -> str:
    days = period_yr * 365.25
    if days < 1.0:   return f"{days * 24:.1f}h"
    if days < 365.25: return f"{days:.1f}d"
    return f"{period_yr:.2f}y"
```

Used by both `_build_stellar_card()` and `_build_orbits_card()`.

### `_build_orbits_card(system, detail_attached)` — Ecc/Incl, Period, and Notes columns

Both header variants include a right-aligned `"Ecc/Incl"` column (after `"AU"`), a
right-aligned `"Period"` column, and a left-aligned `"Notes"` column (last):
- detail_attached: `["Star","Orbit#","AU","Ecc/Incl","Type","Profile","Codes","HZ","Zone","Period","Notes"]` — 11 columns, `right_cols={1,2,3,9}`
- not detail_attached: `["Star","Orbit#","AU","Ecc/Incl","Type","HZ","Zone","Period","Notes"]` — 9 columns, `right_cols={1,2,3,7}`

AU cells show bare `f"{orbit.orbit_au:.3f}"`.

`ecc_incl_str` is the combined display value:
- `ecc_part = f"{orbit.eccentricity:.3f}"` when > 0, else `"—"`
- `incl_part = f"{orbit.inclination:.1f}°"` when > 0, else `"—"`
- `ecc_incl_str = f"{ecc_part}/{incl_part}"` when either is non-zero, else `"—"`

`period_str` is computed as `_fmt_period(orbit.orbit_period_yr)` for non-empty
slots; `"—"` for empty slots or `None`.

`notes_str` is `str(orbit.notes)` when `orbit.notes` is set, `""` otherwise.

### `_orbit_profile(orbit)` — gas giant display safety net

Returns `orbit.gg_sah` for any gas giant orbit before falling through to
`orbit.detail.profile`. This ensures the gas giant's own SAH is shown even if
`attach_detail()` has not run. Part of the Session 24 three-layer fix.

---

## `SystemMapWindow` — non-modal map window

A separate `QMainWindow` opened by the "System Map" button. Multiple windows
can coexist (each click creates a new one).

```python
class SystemMapWindow(QMainWindow):
    _CANVAS_W = 1600       # fixed SVG canvas width

    # Toolbar buttons:
    _theme_btn             # "Light Theme" / "Dark Theme" toggle
    # "Save SVG…" → QFileDialog → writes self._svg_str

    def _render(self) -> None:
        # Calls build_svg(system, canvas_w, palette)
        # Loads result into QSvgWidget inside QScrollArea
        # Falls back to browser + hint label if PySide6.QtSvgWidgets unavailable
```

`_render()` is called at construction and on every theme toggle. `QSvgWidget`
is sized to exact SVG canvas dimensions (`_CANVAS_W × canvas_h`) so
`QScrollArea` provides correct scrollbars for large maps.

---

## Keyboard shortcuts

`QKeySequence::Quit` (Cmd+Q on macOS, Ctrl+Q on Windows/Linux) and
`QKeySequence::Close` (Cmd+W / Ctrl+W) are registered globally on `AppWindow`.
Qt resolves the correct platform key automatically — no manual platform detection
needed.

---

## Pylance type-checking patterns for PySide6

Three patterns used to satisfy Pylance's `"basic"` type checker:

**`QApplication.instance()` narrowing:**
```python
app = QApplication.instance()
if not isinstance(app, QApplication):
    app = QApplication(sys.argv)
```
Using `is not None` leaves the type as `QCoreApplication`, which lacks
`QApplication`-specific methods.

**`takeAt()` and `widget()` guard:**
```python
item = layout.takeAt(0)
if item is not None:
    w = item.widget()
    if w is not None:
        w.deleteLater()
```

**`orbit.world_type` cast:**
```python
type_str: str = str(orbit.world_type)
label = TYPE_LABELS.get(type_str, type_str)
```
Casting to `str` via `str()` lets Pylance resolve the two-argument `dict.get()`
overload and infer `label: str` rather than `str | None`.
