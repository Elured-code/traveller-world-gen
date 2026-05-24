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
    QGroupBox,
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
    generate_unusual_subtype,
    generate_world,
)
from traveller_world_physical import (  # noqa: E402
    generate_world_physical, apply_moon_tidal_effects,
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

_WORLD_TYPE_LABEL = {
    "gas_giant":   "Gas Giant",
    "terrestrial": "Terrestrial",
    "belt":        "Belt",
    "empty":       "Empty",
}

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


def _orbit_profile(orbit: object) -> str:
    cp = getattr(orbit, "canonical_profile", None)
    if cp:
        return cp
    # Gas giant orbits: always show gg_sah (e.g. "GM7") as the profile.
    # When the mainworld is a satellite of the gas giant, attach_detail() sets
    # orbit.detail.sah to the satellite's SAH, hiding the gas giant profile.
    gg_sah = getattr(orbit, "gg_sah", "")
    if gg_sah:
        return gg_sah
    detail = getattr(orbit, "detail", None)
    if detail is None:
        return "—"
    return detail.profile  # type: ignore[attr-defined]


def _fmt_period(period_yr: float) -> str:
    """Format an orbital period: hours, days, or years."""
    days = period_yr * 365.25
    if days < 1.0:
        return f"{days * 24:.1f}h"
    if days < 365.25:
        return f"{days:.1f}d"
    return f"{period_yr:.2f}y"


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

        check_row = QWidget()
        check_layout = QHBoxLayout(check_row)
        check_layout.setSpacing(12)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.addWidget(self._radio_mainworld_only)
        check_layout.addWidget(self._radio_full_detail)
        check_layout.addWidget(self._check_nhz)
        check_layout.addWidget(self._check_oxygen_biomass)
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

        layout.addWidget(grid_widget)
        layout.addStretch()

        self._sector_entry.setEnabled(False)
        self._tm_name_entry.setEnabled(False)
        self._hex_entry.setEnabled(False)

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
        if not checked:
            self._check_nhz.setChecked(False)
            self._check_oxygen_biomass.setChecked(False)
        if self._map_btn is not None:
            self._map_btn.setEnabled(checked)

    def _on_source_toggled(self, checked: bool) -> None:  # pylint: disable=unused-argument
        procedural = self._radio_procedural.isChecked()
        self._sector_entry.setEnabled(not procedural)
        self._tm_name_entry.setEnabled(not procedural)
        self._hex_entry.setEnabled(not procedural)

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
                world.hydrographics, world.size  # type: ignore[attr-defined]
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
                        world.hydrographics, world.size
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

        # Tab 1 — System: stellar + orbits cards in a scroll area
        system_widget = QWidget()
        system_layout = QVBoxLayout(system_widget)
        system_layout.setSpacing(10)
        system_layout.setContentsMargins(4, 4, 4, 4)
        system_layout.addWidget(self._build_stellar_card(system))
        system_layout.addWidget(
            self._build_orbits_card(system, detail_attached=self._detail_attached)
        )
        system_layout.addStretch()

        system_scroll = QScrollArea()
        system_scroll.setWidgetResizable(True)
        system_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        system_scroll.setWidget(system_widget)
        tabs.addTab(system_scroll, "System")

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

    def _build_stellar_card(self, system: object) -> QGroupBox:  # pylint: disable=too-many-locals
        group = QGroupBox("Stellar System")
        outer = QVBoxLayout(group)
        outer.setSpacing(6)
        outer.setContentsMargins(8, 4, 8, 6)

        stars = system.stellar_system.stars  # type: ignore[attr-defined]
        age_gyr = stars[0].age_gyr if stars else 0.0
        age_lbl = QLabel(f"System age: {age_gyr:.2f} Gyr")
        age_lbl.setObjectName("row-label")
        outer.addWidget(age_lbl)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(4)
        grid.setHorizontalSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(grid_widget)

        headers = ["Desig", "Type", "Mass (M☉)", "Temp (K)", "Lum (L☉)", "Orbit (AU)", "Period"]
        right_cols = {2, 3, 4, 5, 6}
        for col, hdr in enumerate(headers):
            lbl = QLabel(hdr)
            lbl.setObjectName("table-header")
            align = (
                Qt.AlignmentFlag.AlignRight
                if col in right_cols
                else Qt.AlignmentFlag.AlignLeft
            )
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, 0, col)

        for row, star in enumerate(stars, start=1):
            orbit_str = f"{star.orbit_au:.3f}" if star.orbit_au else "—"
            period_yr = getattr(star, "orbit_period_yr", None)
            period_str = _fmt_period(period_yr) if period_yr is not None else "—"
            cells = [
                (star.designation,           Qt.AlignmentFlag.AlignLeft),
                (star.classification(),      Qt.AlignmentFlag.AlignLeft),
                (f"{star.mass:.3f}",         Qt.AlignmentFlag.AlignRight),
                (f"{star.temperature:,}",    Qt.AlignmentFlag.AlignRight),
                (f"{star.luminosity:.4f}",   Qt.AlignmentFlag.AlignRight),
                (orbit_str,                  Qt.AlignmentFlag.AlignRight),
                (period_str,                 Qt.AlignmentFlag.AlignRight),
            ]
            for col, (text, align) in enumerate(cells):
                lbl = QLabel(text)
                lbl.setObjectName("table-cell")
                lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(lbl, row, col)

        return group

    def _build_orbits_card(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self, system: object, detail_attached: bool = False
    ) -> QGroupBox:
        group = QGroupBox("System Orbits")
        grid = QGridLayout(group)
        grid.setSpacing(3)
        grid.setHorizontalSpacing(14)

        if detail_attached:
            headers = [
                "Star", "Orbit#", "AU", "Ecc/Incl",
                "Type", "Profile", "Codes", "HZ", "Zone", "Period", "Notes",
            ]
            right_cols = {1, 2, 3, 9}
        else:
            headers = ["Star", "Orbit#", "AU", "Ecc/Incl", "Type", "HZ", "Zone", "Period", "Notes"]
            right_cols = {1, 2, 3, 7}

        for col, hdr in enumerate(headers):
            lbl = QLabel(hdr)
            lbl.setObjectName("table-header")
            align = (
                Qt.AlignmentFlag.AlignRight
                if col in right_cols
                else Qt.AlignmentFlag.AlignLeft
            )
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, 0, col)

        orbits = system.system_orbits.orbits  # type: ignore[attr-defined]
        mw_orbit = system.system_orbits.mainworld_orbit  # type: ignore[attr-defined]

        grid_row = 1
        for orbit in orbits:
            is_mw = orbit is mw_orbit
            is_empty = orbit.world_type == "empty"
            css = "table-mw" if is_mw else ("table-dim" if is_empty else "table-cell")
            hz_str = "★ HZ" if orbit.is_habitable_zone else ""
            _wt = str(orbit.world_type)
            type_str = _WORLD_TYPE_LABEL.get(_wt, _wt)
            zone_str = orbit.temperature_zone.capitalize()

            p_yr = getattr(orbit, "orbit_period_yr", None)
            period_str = _fmt_period(p_yr) if (p_yr is not None and not is_empty) else "—"
            notes_str = str(orbit.notes) if orbit.notes else ""
            if detail_attached and orbit.world_type == "terrestrial":
                _od = getattr(orbit, "detail", None)
                _br = getattr(_od, "biomass_rating", None)
                _bc = getattr(_od, "biocomplexity_rating", None)
                if _br is not None and _br > 0:
                    _bn = f"Biomass {_br}"
                    if _bc is not None:
                        _bn += f", Complexity {_bc}"
                    notes_str = f"{notes_str}, {_bn}" if notes_str else _bn

            ecc_part = f"{orbit.eccentricity:.3f}" if orbit.eccentricity > 0 else "—"
            incl_part = f"{orbit.inclination:.1f}°" if orbit.inclination > 0 else "—"
            ecc_incl_str = (
                f"{ecc_part}/{incl_part}"
                if (orbit.eccentricity > 0 or orbit.inclination > 0)
                else "—"
            )
            if detail_attached:
                detail = getattr(orbit, "detail", None)
                profile_str = _orbit_profile(orbit)
                codes_str = ""
                if is_mw:
                    codes_str = " ".join(
                        getattr(system.mainworld, "trade_codes", [])  # type: ignore[attr-defined]
                    )
                elif detail is not None and not detail.is_gas_giant:  # type: ignore[attr-defined]
                    codes_str = " ".join(detail.trade_codes)  # type: ignore[attr-defined]
                cells: list[tuple[str, Qt.AlignmentFlag]] = [
                    (orbit.star_designation,       Qt.AlignmentFlag.AlignLeft),
                    (f"{orbit.orbit_number:.2f}",  Qt.AlignmentFlag.AlignRight),
                    (f"{orbit.orbit_au:.3f}",      Qt.AlignmentFlag.AlignRight),
                    (ecc_incl_str,                 Qt.AlignmentFlag.AlignRight),
                    (type_str,                     Qt.AlignmentFlag.AlignLeft),
                    (profile_str,                  Qt.AlignmentFlag.AlignLeft),
                    (codes_str,                    Qt.AlignmentFlag.AlignLeft),
                    (hz_str,                       Qt.AlignmentFlag.AlignLeft),
                    (zone_str,                     Qt.AlignmentFlag.AlignLeft),
                    (period_str,                   Qt.AlignmentFlag.AlignRight),
                    (notes_str,                    Qt.AlignmentFlag.AlignLeft),
                ]
            else:
                detail = None
                cells = [
                    (orbit.star_designation,       Qt.AlignmentFlag.AlignLeft),
                    (f"{orbit.orbit_number:.2f}",  Qt.AlignmentFlag.AlignRight),
                    (f"{orbit.orbit_au:.3f}",      Qt.AlignmentFlag.AlignRight),
                    (ecc_incl_str,                 Qt.AlignmentFlag.AlignRight),
                    (type_str,                     Qt.AlignmentFlag.AlignLeft),
                    (hz_str,                       Qt.AlignmentFlag.AlignLeft),
                    (zone_str,                     Qt.AlignmentFlag.AlignLeft),
                    (period_str,                   Qt.AlignmentFlag.AlignRight),
                    (notes_str,                    Qt.AlignmentFlag.AlignLeft),
                ]

            for col, (text, align) in enumerate(cells):
                lbl = QLabel(text)
                lbl.setObjectName(css)
                lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(lbl, grid_row, col)
            grid_row += 1

            if detail_attached and detail is not None:
                for mi, moon in enumerate(detail.moons or [], 1):  # type: ignore[attr-defined]
                    if moon.is_ring:
                        ring_count = moon.ring_count
                        moon_profile = f"R{ring_count:02d}"
                        moon_type = "ring"
                        moon_codes = ""
                    elif moon.detail is not None:
                        moon_profile = moon.detail.profile
                        moon_type = f"size {moon.size_str}"
                        moon_codes = " ".join(moon.detail.trade_codes)
                    else:
                        moon_profile = f"size {moon.size_str}"
                        moon_type = f"size {moon.size_str}"
                        moon_codes = ""
                    moon_pd_str = (
                        f"{moon.orbit_pd:.1f} PD"
                        if moon.orbit_pd is not None else ""
                    )
                    moon_period_str = (
                        _fmt_period(moon.orbit_period_hours / 24 / 365.25)
                        if moon.orbit_period_hours is not None else ""
                    )
                    moon_range_str = (
                        moon.orbit_range.capitalize()
                        if moon.orbit_range else ""
                    )
                    _moon_det = getattr(moon, "detail", None)
                    _moon_br = getattr(_moon_det, "biomass_rating", None)
                    _moon_bc = getattr(_moon_det, "biocomplexity_rating", None)
                    if _moon_br is not None and _moon_br > 0:
                        moon_biomass_note = f"Biomass {_moon_br}"
                        if _moon_bc is not None:
                            moon_biomass_note += f", Complexity {_moon_bc}"
                    else:
                        moon_biomass_note = ""
                    _mecc  = moon.orbit_eccentricity
                    _mincl = moon.orbit_inclination
                    _mecc_part  = f"{_mecc:.3f}" if _mecc > 0 else "—"
                    _mincl_part = f"{_mincl:.1f}°" if _mincl > 0 else "—"
                    moon_ecc_incl = (
                        f"{_mecc_part}/{_mincl_part}"
                        if (_mecc > 0 or _mincl > 0) else ""
                    )
                    moon_cells = [
                        ("",                  Qt.AlignmentFlag.AlignLeft),   # Star
                        (f"↳ m{mi}",         Qt.AlignmentFlag.AlignRight),  # Orbit#
                        (moon_pd_str,         Qt.AlignmentFlag.AlignRight),  # AU col → PD
                        (moon_ecc_incl,       Qt.AlignmentFlag.AlignRight),  # Ecc/Incl
                        (moon_type,           Qt.AlignmentFlag.AlignLeft),   # Type
                        (moon_profile,        Qt.AlignmentFlag.AlignLeft),   # Profile
                        (moon_codes,          Qt.AlignmentFlag.AlignLeft),   # Codes
                        ("",                  Qt.AlignmentFlag.AlignLeft),   # HZ
                        (moon_range_str,      Qt.AlignmentFlag.AlignLeft),   # Zone → range
                        (moon_period_str,     Qt.AlignmentFlag.AlignRight),  # Period
                        (moon_biomass_note,   Qt.AlignmentFlag.AlignLeft),   # Notes
                    ]
                    moon_css = (
                        "table-mw"
                        if is_mw and mi == 1 and orbit.world_type == "gas_giant"
                        else "table-moon"
                    )
                    for col, (text, align) in enumerate(moon_cells):
                        lbl = QLabel(text)
                        lbl.setObjectName(moon_css)
                        lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                        grid.addWidget(lbl, grid_row, col)
                    grid_row += 1

        return group


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
