"""
gen-ui/app.py
=============
Traveller World Generator — Qt desktop UI (PySide6).

Generates mainworlds using the CRB rules in traveller_world_gen.py and
displays the result as a native Qt widget card inside the application window.
World data can also be saved to a user-chosen file in JSON, plain text, or
HTML format via QFileDialog.

PySide6 bundles Qt; no system packages (Homebrew, apt, etc.) are required.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.

AI assistance disclosure: developed with Claude (Anthropic).
The human author reviewed, directed, and is responsible for the code.
"""

# pylint: disable=wrong-import-position,no-name-in-module,import-error,too-many-lines

import os
import random
import secrets
import sys
import tempfile

# Allow importing from the project root when run directly from any directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from system_map import build_svg, PALETTE_DARK, PALETTE_LIGHT  # noqa: E402

try:
    from PySide6.QtSvgWidgets import QSvgWidget as _QSvgWidget  # pylint: disable=ungrouped-imports
    _HAS_SVG_WIDGET = True
except ImportError:
    _HAS_SVG_WIDGET = False

from traveller_map_fetch import AmbiguousWorldError, generate_system_from_map  # noqa: E402
from traveller_system_gen import generate_full_system  # noqa: E402
from traveller_world_detail import (  # noqa: E402
    attach_detail as _attach_detail, gg_diameter_from_sah,
)
from traveller_world_gen import (  # noqa: E402
    generate_atmosphere_detail,
    generate_gas_mix,
    generate_hydrographics,
    generate_unusual_subtype,
    generate_world,
)
from traveller_world_physical import (  # noqa: E402
    generate_world_physical, apply_moon_tidal_effects,
    generate_advanced_mean_temperature,
    check_runaway_greenhouse,
)
from tables import ZONE_CSS_CLASS  # noqa: E402
from traveller_hydro_detail import generate_hydrographic_detail  # noqa: E402

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_CSS = """
QLabel#zone-green   { background-color: #27ae60; color: white;
                      padding: 2px 10px; border-radius: 4px; }
QLabel#zone-amber   { background-color: #e67e22; color: white;
                      padding: 2px 10px; border-radius: 4px; }
QLabel#zone-red     { background-color: #c0392b; color: white;
                      padding: 2px 10px; border-radius: 4px; }
QLabel#uwp-label    { font-family: monospace; font-size: 18pt; font-weight: bold; }
QLabel#world-name   { font-size: 16pt; font-weight: bold; }
QLabel#error-label  { color: #c0392b; font-weight: bold; }
QLabel#hint-label   { font-style: italic; }
QLabel#dim-label    { color: #888888; }
QLabel#stat-value   { font-size: 13pt; font-weight: bold; }
QLabel#stat-sub     { font-size: 9pt; }
QLabel#section-label { font-size: 9pt; font-weight: bold; }
QLabel#row-label    { font-size: 10pt; }
QLabel#row-value    { font-size: 10pt; font-weight: bold; }
QLabel#danger-value { font-size: 10pt; font-weight: bold; color: #c0392b; }
QLabel#tc-badge     { background-color: #faece7; color: #712b13;
                      padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
QLabel#table-header { font-size: 9pt; font-weight: bold; }
QLabel#table-cell   { font-size: 10pt; }
QLabel#table-mw     { font-size: 10pt; font-weight: bold; }
QLabel#table-dim    { font-size: 10pt; color: #9BA3AD; }
QLabel#table-moon   { font-size: 9pt; color: #888888; }
QPushButton#suggested-action { background-color: #3584e4; color: white; }
"""

# Save format definitions: (label, file extension)
_FORMATS = [
    ("JSON",  "json"),
    ("Text",  "txt"),
    ("HTML",  "html"),
]

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _make_hsep(margin_v: int = 0) -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    if margin_v:
        sep.setContentsMargins(0, margin_v, 0, margin_v)
    return sep


def _make_vsep() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep


# ---------------------------------------------------------------------------
# System map window
# ---------------------------------------------------------------------------

_MAP_CANVAS_W = 1600


class SystemMapWindow(QMainWindow):  # pylint: disable=too-few-public-methods
    """Separate, non-modal window that renders an SVG system map."""

    def __init__(self, system: object) -> None:
        super().__init__()
        mw = system.mainworld  # type: ignore[attr-defined]
        name = mw.name if mw else "System"
        self.setWindowTitle(f"System Map — {name}")
        self.resize(min(_MAP_CANVAS_W + 40, 1400), 720)

        self._system = system
        self._palette = PALETTE_DARK
        self._svg_str = ""

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        toolbar = QWidget()
        tbox = QHBoxLayout(toolbar)
        tbox.setContentsMargins(8, 6, 8, 6)
        tbox.setSpacing(8)

        self._theme_btn = QPushButton("Light Theme")
        self._theme_btn.clicked.connect(self._toggle_theme)
        tbox.addWidget(self._theme_btn)

        save_btn = QPushButton("Save SVG…")
        save_btn.clicked.connect(self._on_save)
        tbox.addWidget(save_btn)
        tbox.addStretch()
        vbox.addWidget(toolbar)
        vbox.addWidget(_make_hsep())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        vbox.addWidget(self._scroll, stretch=1)

        self._render()

    def _render(self) -> None:
        svg_str, canvas_h = build_svg(
            self._system, canvas_w=_MAP_CANVAS_W, palette=self._palette
        )
        self._svg_str = svg_str

        if _HAS_SVG_WIDGET:
            widget = _QSvgWidget()  # type: ignore[possibly-undefined]
            widget.load(svg_str.encode("utf-8"))
            widget.setFixedSize(_MAP_CANVAS_W, canvas_h)
            self._scroll.setWidget(widget)
        else:
            try:
                fd, path = tempfile.mkstemp(suffix=".svg", prefix="traveller-map-")
                os.close(fd)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(svg_str)
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                msg = "System map opened in browser (PySide6.QtSvgWidgets not available)."
            except OSError as exc:
                msg = f"Could not write map: {exc}"
            lbl = QLabel(msg)
            lbl.setObjectName("hint-label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll.setWidget(lbl)

    def _toggle_theme(self) -> None:
        if self._palette is PALETTE_DARK:
            self._palette = PALETTE_LIGHT
            self._theme_btn.setText("Dark Theme")
        else:
            self._palette = PALETTE_DARK
            self._theme_btn.setText("Light Theme")
        self._render()

    def _on_save(self) -> None:
        mw = self._system.mainworld  # type: ignore[attr-defined]
        base = (mw.name if mw else "system").replace(" ", "-").lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save System Map", f"{base}-map.svg", "SVG files (*.svg)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._svg_str)
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class AppWindow(QMainWindow):  # pylint: disable=too-few-public-methods,too-many-instance-attributes,attribute-defined-outside-init
    """Main application window for the Traveller World Generator."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Traveller World Generator")
        self.resize(800, 620)
        self._html_path: str | None = None
        self._current_world: object | None = None
        self._current_system: object | None = None
        self._detail_attached: bool = False
        self._seed_auto: bool = False
        self._map_windows: list[object] = []
        self._map_btn: QPushButton | None = None
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(_CSS)
        self._build_ui()
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Quit, self).activated.connect(
            QApplication.instance().quit  # type: ignore[union-attr]
        )
        QShortcut(QKeySequence.StandardKey.Close, self).activated.connect(self.close)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        root.addWidget(self._build_controls())
        root.addWidget(_make_hsep(margin_v=8))
        root.addWidget(self._build_source_row())
        root.addWidget(_make_hsep(margin_v=8))

        self._status_widget = QWidget()
        self._status_layout = QVBoxLayout(self._status_widget)
        self._status_layout.setSpacing(10)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._status_widget, stretch=1)

        self._show_placeholder()

    def _build_controls(self) -> QWidget:
        # pylint: disable=attribute-defined-outside-init
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Name:"))

        self._name_entry = QLineEdit()
        self._name_entry.setPlaceholderText("World name (optional)")
        self._name_entry.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._name_entry.returnPressed.connect(self._on_generate)
        layout.addWidget(self._name_entry)

        layout.addWidget(QLabel("Seed:"))

        self._seed_entry = QLineEdit()
        self._seed_entry.setPlaceholderText("Integer (optional)")
        self._seed_entry.setFixedWidth(140)
        self._seed_entry.returnPressed.connect(self._on_generate)
        self._seed_entry.textChanged.connect(lambda _: self._on_seed_changed())
        layout.addWidget(self._seed_entry)

        clear_btn = QPushButton("New Seed")
        clear_btn.clicked.connect(self._on_clear_seed)
        layout.addWidget(clear_btn)

        btn = QPushButton("Generate")
        btn.setObjectName("suggested-action")
        btn.clicked.connect(self._on_generate)
        layout.addWidget(btn)

        return row

    def _build_source_row(self) -> QWidget:  # pylint: disable=too-many-locals,too-many-statements
        # pylint: disable=attribute-defined-outside-init
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left column: radio buttons stacked above checkboxes
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(6)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._radio_procedural = QRadioButton("Procedural")
        self._radio_travellermap = QRadioButton("TravellerMap")
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._radio_procedural)
        self._radio_group.addButton(self._radio_travellermap)
        self._radio_procedural.setChecked(True)
        self._radio_procedural.toggled.connect(self._on_source_toggled)

        radio_row = QWidget()
        radio_layout = QHBoxLayout(radio_row)
        radio_layout.setSpacing(12)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.addWidget(self._radio_procedural)
        radio_layout.addWidget(self._radio_travellermap)
        left_layout.addWidget(radio_row)

        self._radio_mainworld_only = QRadioButton("Mainworld only")
        self._radio_full_detail = QRadioButton("Full detail")
        self._detail_group = QButtonGroup(self)
        self._detail_group.addButton(self._radio_mainworld_only)
        self._detail_group.addButton(self._radio_full_detail)
        self._radio_mainworld_only.setChecked(True)
        self._radio_full_detail.toggled.connect(self._on_detail_toggled)
        self._check_nhz = QCheckBox("NHZ Atmospheres")
        self._check_nhz.setEnabled(False)
        self._check_oxygen_biomass = QCheckBox("Oxygen requires biomass")
        self._check_oxygen_biomass.setEnabled(False)
        self._check_advanced_temp = QCheckBox("Advanced temperature")
        self._check_advanced_temp.setEnabled(False)
        self._check_runaway_greenhouse = QCheckBox("Runaway greenhouse")
        self._check_runaway_greenhouse.setEnabled(False)

        check_row = QWidget()
        check_layout = QHBoxLayout(check_row)
        check_layout.setSpacing(12)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.addWidget(self._radio_mainworld_only)
        check_layout.addWidget(self._radio_full_detail)
        check_layout.addWidget(self._check_nhz)
        check_layout.addWidget(self._check_oxygen_biomass)
        check_layout.addWidget(self._check_advanced_temp)
        check_layout.addWidget(self._check_runaway_greenhouse)
        left_layout.addWidget(check_row)

        layout.addWidget(left, 0, Qt.AlignmentFlag.AlignTop)

        vsep = _make_vsep()
        vsep.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(vsep)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        sector_lbl = QLabel("Sector:")
        sector_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._sector_entry = QLineEdit()
        self._sector_entry.setPlaceholderText("e.g. Spinward Marches")
        self._sector_entry.setFixedWidth(180)
        grid.addWidget(sector_lbl, 0, 0)
        grid.addWidget(self._sector_entry, 0, 1)

        name_lbl = QLabel("Name:")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._tm_name_entry = QLineEdit()
        self._tm_name_entry.setPlaceholderText("e.g. Regina")
        self._tm_name_entry.setFixedWidth(120)
        self._tm_name_entry.returnPressed.connect(self._on_generate)
        grid.addWidget(name_lbl, 0, 2)
        grid.addWidget(self._tm_name_entry, 0, 3)

        hex_lbl = QLabel("Hex:")
        hex_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._hex_entry = QLineEdit()
        self._hex_entry.setPlaceholderText("e.g. 1910")
        self._hex_entry.setFixedWidth(60)
        self._hex_entry.returnPressed.connect(self._on_generate)
        optional_lbl = QLabel("Optional")
        optional_lbl.setObjectName("hint-label")
        grid.addWidget(hex_lbl, 1, 2)
        grid.addWidget(self._hex_entry, 1, 3)
        grid.addWidget(optional_lbl, 1, 4)

        self._tm_vsep = vsep
        self._tm_panel = grid_widget
        layout.addWidget(grid_widget)
        layout.addStretch()

        self._tm_panel.setVisible(False)
        self._tm_vsep.setVisible(False)

        return row

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_clear_seed(self) -> None:
        self._seed_auto = False
        self._seed_entry.setText(str(secrets.randbelow(2 ** 31)))

    def _on_seed_changed(self) -> None:
        if not self._seed_auto:
            return
        self._seed_auto = False

    def _on_detail_toggled(self, checked: bool) -> None:
        self._check_nhz.setEnabled(checked)
        self._check_oxygen_biomass.setEnabled(checked)
        self._check_advanced_temp.setEnabled(checked)
        self._check_runaway_greenhouse.setEnabled(checked)
        if not checked:
            self._check_nhz.setChecked(False)
            self._check_oxygen_biomass.setChecked(False)
            self._check_advanced_temp.setChecked(False)
            self._check_runaway_greenhouse.setChecked(False)
        if self._map_btn is not None:
            self._map_btn.setEnabled(checked)

    def _on_source_toggled(self, checked: bool) -> None:  # pylint: disable=unused-argument
        procedural = self._radio_procedural.isChecked()
        self._tm_panel.setVisible(not procedural)
        self._tm_vsep.setVisible(not procedural)

    def _on_generate(self) -> None:
        name = self._name_entry.text().strip() or "Unknown"
        seed_raw = self._seed_entry.text().strip()

        if seed_raw and not self._seed_auto:
            try:
                seed = int(seed_raw)
            except ValueError:
                self._show_error("Seed must be an integer.")
                return
        else:
            seed = secrets.randbelow(2 ** 31)

        random.seed(seed)
        self._seed_entry.blockSignals(True)
        self._seed_entry.setText(str(seed))
        self._seed_entry.blockSignals(False)
        self._seed_auto = True

        full_system = self._radio_full_detail.isChecked()
        attach_detail_flag = full_system

        if self._radio_travellermap.isChecked():
            sector = self._sector_entry.text().strip()
            search_name = self._tm_name_entry.text().strip() or None
            hex_pos = self._hex_entry.text().strip() or None
            if not sector:
                self._show_error("Sector is required for TravellerMap lookup.")
                return
            if not search_name and not hex_pos:
                self._show_error("Enter a world name or hex for TravellerMap lookup.")
                return
            self._do_travellermap_generation(
                sector, search_name, hex_pos, seed, full_system, attach_detail_flag,
                orbital_eccentricity=True,
                orbital_inclination=True,
            )
        else:
            if full_system:
                system = generate_full_system(
                    name, seed=seed,
                    nhz_atmospheres=self._check_nhz.isChecked(),
                    orbital_eccentricity=True,
                    orbital_inclination=True,
                )
                self._finish_system_generation(system, attach_detail_flag)
            else:
                world = generate_world(name)
                self._finish_generation(world)

    def _do_travellermap_generation(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        sector: str,
        search_name: "str | None",
        hex_pos: "str | None",
        seed: int,
        full_system: bool = False,
        attach_detail_flag: bool = False,
        orbital_eccentricity: bool = False,
        orbital_inclination: bool = False,
    ) -> None:
        try:
            system = generate_system_from_map(
                name=search_name,
                sector=sector,
                hex_pos=hex_pos,
                seed=seed,
                orbital_eccentricity=orbital_eccentricity,
                orbital_inclination=orbital_inclination,
            )
        except AmbiguousWorldError as exc:
            self._show_disambiguation_dialog(exc, seed, full_system, attach_detail_flag)
            return
        except (ValueError, LookupError, ConnectionError) as exc:
            self._show_error(str(exc))
            return
        if full_system:
            self._finish_system_generation(system, attach_detail_flag)
        else:
            world = system.mainworld
            if world is None:
                self._show_error("TravellerMap lookup returned no mainworld.")
                return
            self._finish_generation(world)

    def _finish_generation(self, world: object) -> None:
        self._current_system = None
        self._current_world = world
        if world.atmosphere_detail is None:  # type: ignore[attr-defined]
            world.atmosphere_detail = generate_atmosphere_detail(  # type: ignore[attr-defined]
                world.atmosphere, world.size,  # type: ignore[attr-defined]
                temperature=world.temperature,  # type: ignore[attr-defined]
            )
            generate_gas_mix(
                world.atmosphere_detail,  # type: ignore[attr-defined]
                world.atmosphere, world.size,  # type: ignore[attr-defined]
                world.temperature, None,  # type: ignore[attr-defined]
                world.hydrographics,  # type: ignore[attr-defined]
            )
            generate_unusual_subtype(
                world.atmosphere_detail, world.atmosphere,  # type: ignore[attr-defined]
                world.size, world.hydrographics,  # type: ignore[attr-defined]
            )
        if world.hydrographic_detail is None:  # type: ignore[attr-defined]
            world.hydrographic_detail = generate_hydrographic_detail(  # type: ignore[attr-defined]
                world.hydrographics, world.size,  # type: ignore[attr-defined]
                atmosphere=world.atmosphere,  # type: ignore[attr-defined]
                temperature=world.temperature,  # type: ignore[attr-defined]
            )
        path = self._write_html(world.to_html())  # type: ignore[attr-defined]
        if path is not None:
            self._html_path = path
        self._show_summary(world)

    def _finish_system_generation(  # pylint: disable=too-many-locals
        self, system: object, attach_detail_flag: bool = False
    ) -> None:
        self._current_system = system
        self._current_world = system.mainworld  # type: ignore[attr-defined]
        if attach_detail_flag:
            world = system.mainworld  # type: ignore[attr-defined]
            mw_orbit = system.mainworld_orbit  # type: ignore[attr-defined]
            if world is not None:
                stars = system.stellar_system.stars  # type: ignore[attr-defined]
                age = stars[0].age_gyr if stars else 0.0
                orbit_number = mw_orbit.orbit_number if mw_orbit is not None else None
                orbit_au = mw_orbit.orbit_au if mw_orbit is not None else None
                star_mass = stars[0].mass if stars else None
                world.size_detail = generate_world_physical(
                    world, age, orbit_number, orbit_au, star_mass,
                    hz_deviation=mw_orbit.hz_deviation if mw_orbit is not None else None,
                )
                if world.atmosphere_detail is None:
                    hz_dev = mw_orbit.hz_deviation if mw_orbit is not None else None
                    world.atmosphere_detail = generate_atmosphere_detail(
                        world.atmosphere, world.size, age,
                        temperature=world.temperature,
                        hz_deviation=hz_dev,
                    )
                    generate_gas_mix(
                        world.atmosphere_detail, world.atmosphere, world.size,
                        world.temperature, hz_dev, world.hydrographics,
                    )
                    generate_unusual_subtype(
                        world.atmosphere_detail, world.atmosphere,
                        world.size, world.hydrographics,
                    )
                if world.hydrographic_detail is None:
                    world.hydrographic_detail = generate_hydrographic_detail(
                        world.hydrographics, world.size,
                        atmosphere=world.atmosphere,
                        temperature=world.temperature,
                    )
                # Advanced temperature computed before attach_detail so that
                # high_temp_k and advanced_mean_temperature_k are available to
                # the biomass DM calculation inside _apply_biomass().
                if (self._check_advanced_temp.isChecked()
                        and world.size_detail is not None
                        and mw_orbit is not None):
                    mw_au = mw_orbit.orbit_au
                    interior_lum = sum(
                        s.luminosity for s in stars
                        if s.orbit_au <= 0.0 or s.orbit_au < mw_au
                    )
                    pb = world.atmosphere_detail.pressure_bar if world.atmosphere_detail else None
                    generate_advanced_mean_temperature(
                        world.size_detail,
                        atmosphere=world.atmosphere,
                        hydrographics=world.hydrographics,
                        pressure_bar=pb,
                        luminosity=interior_lum,
                        orbit_au=mw_au,
                        hz_deviation=mw_orbit.hz_deviation,
                        orbit_eccentricity=mw_orbit.eccentricity,
                        star_mass=stars[0].mass if stars else 1.0,
                    )
                    self._maybe_apply_runaway_greenhouse(
                        world, stars, mw_orbit, interior_lum, mw_au
                    )
            _attach_detail(  # type: ignore[arg-type]
                system,
                optional_biomass_rule=self._check_oxygen_biomass.isChecked(),
            )
            if world is not None and world.size_detail is not None and mw_orbit is not None:
                det = mw_orbit.detail
                if det is not None:
                    _is_moon = mw_orbit.world_type == "gas_giant"
                    if _is_moon:
                        first = det.moons[0] if det.moons else None
                        moons = first.detail.moons if first and first.detail else []
                        _gg_sat = det.moons[0] if det.moons else None
                        _gg_m_e = float(
                            gg_diameter_from_sah(  # type: ignore[attr-defined]
                                getattr(mw_orbit, "gg_sah", "")
                            ) ** 2
                        ) if getattr(mw_orbit, "gg_sah", "") else 0.0
                    else:
                        moons = det.moons or []
                        _gg_sat = None
                        _gg_m_e = 0.0
                    stars = system.stellar_system.stars  # type: ignore[attr-defined]
                    apply_moon_tidal_effects(
                        world.size_detail,
                        moons=moons,
                        world_size=world.size,
                        world_atmosphere=world.atmosphere,
                        age_gyr=stars[0].age_gyr if stars else 0.0,
                        orbit_number=mw_orbit.orbit_number,
                        orbit_au=mw_orbit.orbit_au,
                        star_mass=stars[0].mass if stars else 1.0,
                        orbit_eccentricity=mw_orbit.eccentricity,
                        is_moon=_is_moon,
                        gg_mass_earth=_gg_m_e,
                        gg_satellite_moon=_gg_sat,
                    )
        self._detail_attached = attach_detail_flag
        path = self._write_html(
            system.to_html(detail_attached=attach_detail_flag)  # type: ignore[attr-defined]
        )
        if path is not None:
            self._html_path = path
        self._show_system_summary(system)

    def _show_disambiguation_dialog(  # pylint: disable=too-many-locals
        self,
        error: AmbiguousWorldError,
        seed: int,
        full_system: bool = False,
        attach_detail_flag: bool = False,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Ambiguous World Name")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(
            f"Multiple worlds named '{error.name}' found in {error.sector}."
            f"\nSelect one:"
        )
        layout.addWidget(lbl)

        radio_group = QButtonGroup(dialog)
        radios: list[tuple[QRadioButton, str]] = []
        for i, (world_name, hex_code) in enumerate(error.candidates):
            radio = QRadioButton(f"{world_name}  —  hex {hex_code}")
            if i == 0:
                radio.setChecked(True)
            radio_group.addButton(radio)
            radios.append((radio, hex_code))
            layout.addWidget(radio)

        layout.addWidget(_make_hsep(margin_v=4))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = next((h for radio, h in radios if radio.isChecked()), None)
            if selected:
                self._do_travellermap_generation(
                    error.sector, None, selected, seed, full_system, attach_detail_flag,
                    orbital_eccentricity=True,
                    orbital_inclination=True,
                )

    def _on_map_clicked(self) -> None:
        if self._current_system is None:
            return
        win = SystemMapWindow(self._current_system)
        self._map_windows.append(win)
        win.show()

    def _on_save_clicked(self) -> None:
        obj = self._current_system or self._current_world
        if obj is None:
            return

        idx = self._format_dropdown.currentIndex()
        label, ext = _FORMATS[idx]

        base_name = getattr(self._current_world, "name", None) or "world"
        if self._current_system is not None:
            base_name += "-system"
        safe_name = base_name.replace(" ", "-").lower()

        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save World Data as {label}",
            f"{safe_name}.{ext}",
            f"{label} files (*.{ext})",
        )
        if not path:
            return

        if ext == "json":
            content = obj.to_json()  # type: ignore[attr-defined]
        elif ext == "txt":
            content = obj.summary()  # type: ignore[attr-defined]
        else:
            if self._current_system is not None:
                content = obj.to_html(  # type: ignore[attr-defined]
                    detail_attached=self._detail_attached
                )
            else:
                content = obj.to_html()  # type: ignore[attr-defined]

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            self._show_error(f"Save failed: {exc}")

    # ------------------------------------------------------------------
    # HTML file management
    # ------------------------------------------------------------------

    def _write_html(self, html: str) -> str | None:
        if self._html_path and os.path.exists(self._html_path):
            try:
                os.unlink(self._html_path)
            except OSError:
                pass
        try:
            fd, path = tempfile.mkstemp(suffix=".html", prefix="traveller-world-")
            os.close(fd)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            return path
        except OSError:
            return None

    @staticmethod
    def _open_in_browser(path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ------------------------------------------------------------------
    # Status panel
    # ------------------------------------------------------------------

    def _clear_status(self) -> None:
        self._map_btn = None
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _show_placeholder(self) -> None:
        self._clear_status()
        lbl = QLabel("Enter a name and click Generate.")
        lbl.setObjectName("dim-label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_layout.addStretch()
        self._status_layout.addWidget(lbl)
        self._status_layout.addStretch()

    def _show_error(self, message: str) -> None:
        self._clear_status()
        lbl = QLabel(message)
        lbl.setObjectName("error-label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_layout.addStretch()
        self._status_layout.addWidget(lbl)
        self._status_layout.addStretch()

    def _show_summary(self, world: object) -> None:
        self._clear_status()
        self._status_layout.addWidget(self._build_summary_header(world))
        self._status_layout.addWidget(_make_hsep(margin_v=6))
        view = QWebEngineView()
        view.setHtml(world.to_html())  # type: ignore[attr-defined]
        view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._status_layout.addWidget(view, stretch=1)

    def _show_system_summary(self, system: object) -> None:
        self._clear_status()
        mw = system.mainworld  # type: ignore[attr-defined]

        header = self._build_system_summary_header(system)
        self._status_layout.addWidget(header)
        self._status_layout.addWidget(_make_hsep(margin_v=6))

        tabs = QTabWidget()
        tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Tab 1 — System: HTML view via system.to_html()
        system_view = QWebEngineView()
        system_view.setHtml(
            system.to_html(detail_attached=self._detail_attached)  # type: ignore[attr-defined]
        )
        system_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        tabs.addTab(system_view, "System")

        # Tab 2 — Mainworld: world card HTML view
        if mw is not None:
            mw_view = QWebEngineView()
            mw_view.setHtml(mw.to_html())  # type: ignore[attr-defined]
            mw_view.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            tabs.addTab(mw_view, "Mainworld")
            tabs.setCurrentIndex(1)

        self._status_layout.addWidget(tabs, stretch=1)

    def _build_system_summary_header(self, system: object) -> QWidget:
        mw = system.mainworld  # type: ignore[attr-defined]
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        if mw is not None:
            name_lbl = QLabel(mw.name)
            name_lbl.setObjectName("world-name")
            layout.addWidget(name_lbl)

            uwp_lbl = QLabel(mw.uwp())
            uwp_lbl.setObjectName("uwp-label")
            layout.addWidget(uwp_lbl)

            zone_lbl = QLabel(f"  {mw.travel_zone}  ")
            zone_lbl.setObjectName(
                ZONE_CSS_CLASS.get(mw.travel_zone, "zone-green")
            )
            layout.addWidget(zone_lbl)
        else:
            stars = system.stellar_system.stars  # type: ignore[attr-defined]
            lbl = QLabel(f"System — {len(stars)} star(s)")
            lbl.setObjectName("world-name")
            layout.addWidget(lbl)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(spacer)

        map_btn = QPushButton("System Map")
        map_btn.clicked.connect(self._on_map_clicked)
        map_btn.setEnabled(self._radio_full_detail.isChecked())
        self._map_btn = map_btn
        layout.addWidget(map_btn)

        vsep = _make_vsep()
        vsep.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(vsep)

        layout.addWidget(self._build_action_buttons())
        return header

    def _build_action_buttons(self) -> QWidget:
        # pylint: disable=attribute-defined-outside-init
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        open_btn = QPushButton("Open in Browser")
        open_btn.clicked.connect(
            lambda: self._open_in_browser(self._html_path)
            if self._html_path
            else None
        )
        layout.addWidget(open_btn)

        vsep = _make_vsep()
        vsep.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(vsep)

        layout.addWidget(QLabel("Save as:"))

        self._format_dropdown = QComboBox()
        for lbl, _ in _FORMATS:
            self._format_dropdown.addItem(lbl)
        layout.addWidget(self._format_dropdown)

        save_btn = QPushButton("Save…")
        save_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(save_btn)

        return box

    def _build_summary_header(self, world: object) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(world.name)  # type: ignore[attr-defined]
        name_lbl.setObjectName("world-name")
        layout.addWidget(name_lbl)

        uwp_lbl = QLabel(world.uwp())  # type: ignore[attr-defined]
        uwp_lbl.setObjectName("uwp-label")
        layout.addWidget(uwp_lbl)

        zone_lbl = QLabel(f"  {world.travel_zone}  ")  # type: ignore[attr-defined]
        zone_lbl.setObjectName(
            ZONE_CSS_CLASS.get(world.travel_zone, "zone-green")  # type: ignore[attr-defined]
        )
        layout.addWidget(zone_lbl)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(spacer)

        layout.addWidget(self._build_action_buttons())
        return header

    def _maybe_apply_runaway_greenhouse(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, world: object, stars: list,
            mw_orbit: object, interior_lum: float, mw_au: float,
    ) -> None:
        """Apply optional runaway greenhouse mutations (WBH p.79)."""
        if not self._check_runaway_greenhouse.isChecked():
            return
        if (world.size_detail is None  # type: ignore[attr-defined]
                or world.size_detail.advanced_mean_temperature_k is None):  # type: ignore
            return
        rg = check_runaway_greenhouse(
            atmosphere=world.atmosphere,  # type: ignore[attr-defined]
            temp_k=world.size_detail.advanced_mean_temperature_k,  # type: ignore
            age_gyr=stars[0].age_gyr if stars else 0.0,
            size=world.size,  # type: ignore[attr-defined]
        )
        if rg is None:
            return
        world.size_detail.runaway_greenhouse = True  # type: ignore
        if rg.new_atmosphere is not None:
            world.atmosphere = rg.new_atmosphere  # type: ignore
        world.temperature = "Boiling"  # type: ignore
        world.hydrographics = generate_hydrographics(  # type: ignore
            world.size, world.atmosphere, "Boiling"  # type: ignore
        )
        world.hydrographic_detail = generate_hydrographic_detail(  # type: ignore
            world.hydrographics, world.size,  # type: ignore
            atmosphere=world.atmosphere,  # type: ignore
            temperature="Boiling",
        )
        rg_pb = (
            world.atmosphere_detail.pressure_bar  # type: ignore
            if world.atmosphere_detail else None  # type: ignore
        )
        generate_advanced_mean_temperature(
            world.size_detail,  # type: ignore
            atmosphere=world.atmosphere,  # type: ignore
            hydrographics=world.hydrographics,  # type: ignore
            pressure_bar=rg_pb,
            luminosity=interior_lum,
            orbit_au=mw_au,
            hz_deviation=mw_orbit.hz_deviation,  # type: ignore
            orbit_eccentricity=mw_orbit.eccentricity,  # type: ignore
            star_mass=stars[0].mass if stars else 1.0,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the Traveller World Generator desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Traveller World Generator")
    window = AppWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
