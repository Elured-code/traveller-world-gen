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

import os
import random
import secrets
import sys
import tempfile

# Allow importing from the project root when run directly from any directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut  # noqa: E402
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
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from traveller_map_fetch import AmbiguousWorldError, generate_system_from_map  # noqa: E402
from traveller_system_gen import generate_full_system  # noqa: E402
from traveller_world_detail import attach_detail as _attach_detail  # noqa: E402
from traveller_world_gen import (  # noqa: E402
    STARPORT_FACILITY_DETAIL,
    STARPORT_QUALITY_LABEL,
    generate_world,
    to_hex as _to_hex,
)

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

_ZONE_OBJECT_NAME = {"Green": "zone-green", "Amber": "zone-amber", "Red": "zone-red"}

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

_TRADE_CODE_FULL = {
    "Ag": "Agricultural",   "As": "Asteroid",      "Ba": "Barren",
    "De": "Desert",         "Fl": "Fluid Oceans",   "Ga": "Garden",
    "Hi": "High Pop.",      "Ht": "High Tech",      "Ic": "Ice-Capped",
    "In": "Industrial",     "Lo": "Low Pop.",       "Lt": "Low Tech",
    "Na": "Non-Ag.",        "Ni": "Non-Industrial", "Po": "Poor",
    "Ri": "Rich",           "Va": "Vacuum",         "Wa": "Waterworld",
}

_BASE_FULL = {
    "N": "N — Naval", "S": "S — Scout",   "M": "M — Military",
    "H": "H — Highport", "C": "C — Corsair",
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
    detail = getattr(orbit, "detail", None)
    if detail is None:
        return "—"
    return detail.profile  # type: ignore[attr-defined]


def _tl_era(tl: int) -> str:
    if tl <= 3:  return "Primitive"
    if tl <= 6:  return "Industrial"
    if tl <= 9:  return "Pre-Stellar"
    if tl <= 11: return "Early Stellar"
    if tl <= 14: return "Average Stellar"
    return "High Stellar"


def _detail_row(label_text: str, value_text: str, danger: bool = False) -> QWidget:
    """One label/value row for the Physical and Society detail cards."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(8)
    lbl = QLabel(label_text)
    lbl.setObjectName("row-label")
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    val = QLabel(value_text)
    val.setObjectName("danger-value" if danger else "row-value")
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setWordWrap(True)
    val.setMaximumWidth(200)
    layout.addWidget(lbl)
    layout.addWidget(val)
    return row


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class AppWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Traveller World Generator")
        self.resize(800, 620)
        self._html_path: str | None = None
        self._current_world: object | None = None
        self._current_system: object | None = None
        self._detail_attached: bool = False
        self._seed_auto: bool = False
        app = QApplication.instance()
        if app is not None:
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
        root.addWidget(self._build_options_row())
        root.addWidget(_make_hsep(margin_v=8))

        self._status_widget = QWidget()
        self._status_layout = QVBoxLayout(self._status_widget)
        self._status_layout.setSpacing(10)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._status_widget, stretch=1)

        self._show_placeholder()

    def _build_controls(self) -> QWidget:
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

    def _build_source_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        self._radio_procedural = QRadioButton("Procedural")
        self._radio_travellermap = QRadioButton("TravellerMap")
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._radio_procedural)
        self._radio_group.addButton(self._radio_travellermap)
        self._radio_procedural.setChecked(True)
        self._radio_procedural.toggled.connect(self._on_source_toggled)

        layout.addWidget(self._radio_procedural)
        layout.addWidget(self._radio_travellermap)

        vsep = _make_vsep()
        vsep.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(vsep)

        sector_lbl = QLabel("Sector:")
        sector_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(sector_lbl)
        self._sector_entry = QLineEdit()
        self._sector_entry.setPlaceholderText("e.g. Spinward Marches")
        self._sector_entry.setFixedWidth(180)
        layout.addWidget(self._sector_entry)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel("Name:")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._tm_name_entry = QLineEdit()
        self._tm_name_entry.setPlaceholderText("e.g. Regina")
        self._tm_name_entry.setFixedWidth(120)
        self._tm_name_entry.returnPressed.connect(self._on_generate)
        grid.addWidget(name_lbl, 0, 0)
        grid.addWidget(self._tm_name_entry, 0, 1)

        hex_lbl = QLabel("Hex:")
        hex_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._hex_entry = QLineEdit()
        self._hex_entry.setPlaceholderText("e.g. 1910")
        self._hex_entry.setFixedWidth(60)
        self._hex_entry.returnPressed.connect(self._on_generate)
        optional_lbl = QLabel("Optional")
        optional_lbl.setObjectName("hint-label")
        grid.addWidget(hex_lbl, 1, 0)
        grid.addWidget(self._hex_entry, 1, 1)
        grid.addWidget(optional_lbl, 1, 2)

        layout.addWidget(grid_widget)
        layout.addStretch()

        self._sector_entry.setEnabled(False)
        self._tm_name_entry.setEnabled(False)
        self._hex_entry.setEnabled(False)

        return row

    def _build_options_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        self._check_full_system = QCheckBox("Full system")
        self._check_full_system.toggled.connect(self._on_full_system_toggled)
        layout.addWidget(self._check_full_system)

        self._check_attach_detail = QCheckBox("Attach detail")
        self._check_attach_detail.setEnabled(False)
        layout.addWidget(self._check_attach_detail)

        layout.addStretch()
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

    def _on_full_system_toggled(self, checked: bool) -> None:
        self._check_attach_detail.setEnabled(checked)
        if not checked:
            self._check_attach_detail.setChecked(False)

    def _on_source_toggled(self, checked: bool) -> None:
        if not checked:
            return
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
        self._seed_auto = True
        self._seed_entry.setText(str(seed))

        full_system = self._check_full_system.isChecked()
        attach_detail_flag = full_system and self._check_attach_detail.isChecked()

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
                sector, search_name, hex_pos, seed, full_system, attach_detail_flag
            )
        else:
            if full_system:
                system = generate_full_system(name, seed=seed)
                self._finish_system_generation(system, attach_detail_flag)
            else:
                world = generate_world(name)
                self._finish_generation(world)

    def _do_travellermap_generation(
        self,
        sector: str,
        search_name: "str | None",
        hex_pos: "str | None",
        seed: int,
        full_system: bool = False,
        attach_detail_flag: bool = False,
    ) -> None:
        try:
            system = generate_system_from_map(
                name=search_name,
                sector=sector,
                hex_pos=hex_pos,
                seed=seed,
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
        path = self._write_html(world.to_html())  # type: ignore[attr-defined]
        if path is not None:
            self._html_path = path
        self._show_summary(world)

    def _finish_system_generation(
        self, system: object, attach_detail_flag: bool = False
    ) -> None:
        self._current_system = system
        self._current_world = system.mainworld  # type: ignore[attr-defined]
        if attach_detail_flag:
            _attach_detail(system)  # type: ignore[arg-type]
        self._detail_attached = attach_detail_flag
        path = self._write_html(
            system.to_html(detail_attached=attach_detail_flag)  # type: ignore[attr-defined]
        )
        if path is not None:
            self._html_path = path
        self._show_system_summary(system)

    def _show_disambiguation_dialog(
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
                    error.sector, None, selected, seed, full_system, attach_detail_flag
                )

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
                content = obj.to_html(detail_attached=self._detail_attached)  # type: ignore[attr-defined]
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
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        scroll.setWidget(self._build_world_card(world))
        self._status_layout.addWidget(scroll, stretch=1)

    def _show_system_summary(self, system: object) -> None:
        self._clear_status()
        mw = system.mainworld  # type: ignore[attr-defined]

        header, orbit_toggle = self._build_system_summary_header(system)
        self._status_layout.addWidget(header)
        self._status_layout.addWidget(_make_hsep(margin_v=6))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(4, 4, 4, 4)

        stellar_card = self._build_stellar_card(system)
        orbits_card = self._build_orbits_card(
            system, detail_attached=self._detail_attached
        )
        card_layout.addWidget(stellar_card)
        card_layout.addWidget(orbits_card)

        if mw is not None:
            mw_group = QGroupBox("Mainworld")
            mw_inner = QVBoxLayout(mw_group)
            mw_inner.addWidget(self._build_world_card(mw))
            card_layout.addWidget(mw_group)

        card_layout.addStretch()
        scroll.setWidget(card)
        self._status_layout.addWidget(scroll, stretch=1)

        def _on_orbit_toggle(checked: bool) -> None:
            stellar_card.setVisible(checked)
            orbits_card.setVisible(checked)

        orbit_toggle.toggled.connect(_on_orbit_toggle)

    def _build_system_summary_header(
        self, system: object
    ) -> "tuple[QWidget, QCheckBox]":
        mw = system.mainworld  # type: ignore[attr-defined]
        bar = QWidget()
        layout = QHBoxLayout(bar)
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
                _ZONE_OBJECT_NAME.get(mw.travel_zone, "zone-green")
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

        orbit_toggle = QCheckBox("Stellar && Orbits")
        orbit_toggle.setChecked(True)
        layout.addWidget(orbit_toggle)

        vsep = _make_vsep()
        vsep.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(vsep)

        layout.addWidget(self._build_action_buttons())
        return bar, orbit_toggle

    def _build_action_buttons(self) -> QWidget:
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
        bar = QWidget()
        layout = QHBoxLayout(bar)
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
            _ZONE_OBJECT_NAME.get(world.travel_zone, "zone-green")  # type: ignore[attr-defined]
        )
        layout.addWidget(zone_lbl)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(spacer)

        layout.addWidget(self._build_action_buttons())
        return bar

    def _build_stellar_card(self, system: object) -> QGroupBox:
        group = QGroupBox("Stellar System")
        grid = QGridLayout(group)
        grid.setSpacing(4)
        grid.setHorizontalSpacing(16)

        headers = ["Desig", "Type", "Mass (M☉)", "Temp (K)", "Lum (L☉)", "Orbit (AU)"]
        right_cols = {2, 3, 4, 5}
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

        stars = system.stellar_system.stars  # type: ignore[attr-defined]
        for row, star in enumerate(stars, start=1):
            orbit_str = f"{star.orbit_au:.3f}" if star.orbit_au else "—"
            cells = [
                (star.designation,           Qt.AlignmentFlag.AlignLeft),
                (star.classification(),      Qt.AlignmentFlag.AlignLeft),
                (f"{star.mass:.3f}",         Qt.AlignmentFlag.AlignRight),
                (f"{star.temperature:,}",    Qt.AlignmentFlag.AlignRight),
                (f"{star.luminosity:.4f}",   Qt.AlignmentFlag.AlignRight),
                (orbit_str,                  Qt.AlignmentFlag.AlignRight),
            ]
            for col, (text, align) in enumerate(cells):
                lbl = QLabel(text)
                lbl.setObjectName("table-cell")
                lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(lbl, row, col)

        return group

    def _build_orbits_card(
        self, system: object, detail_attached: bool = False
    ) -> QGroupBox:
        group = QGroupBox("System Orbits")
        grid = QGridLayout(group)
        grid.setSpacing(3)
        grid.setHorizontalSpacing(14)

        if detail_attached:
            headers = ["Star", "Orbit#", "AU", "Type", "Profile", "Codes", "HZ", "Zone"]
            right_cols = {1, 2}
        else:
            headers = ["Star", "Orbit#", "AU", "Type", "HZ", "Zone"]
            right_cols = {1, 2}

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
            type_str = _WORLD_TYPE_LABEL.get(orbit.world_type, orbit.world_type)
            zone_str = orbit.temperature_zone.capitalize()

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
                    (type_str,                     Qt.AlignmentFlag.AlignLeft),
                    (profile_str,                  Qt.AlignmentFlag.AlignLeft),
                    (codes_str,                    Qt.AlignmentFlag.AlignLeft),
                    (hz_str,                       Qt.AlignmentFlag.AlignLeft),
                    (zone_str,                     Qt.AlignmentFlag.AlignLeft),
                ]
            else:
                detail = None
                cells = [
                    (orbit.star_designation,       Qt.AlignmentFlag.AlignLeft),
                    (f"{orbit.orbit_number:.2f}",  Qt.AlignmentFlag.AlignRight),
                    (f"{orbit.orbit_au:.3f}",      Qt.AlignmentFlag.AlignRight),
                    (type_str,                     Qt.AlignmentFlag.AlignLeft),
                    (hz_str,                       Qt.AlignmentFlag.AlignLeft),
                    (zone_str,                     Qt.AlignmentFlag.AlignLeft),
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
                        ring_count = getattr(moon, "_ring_count", 1)
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
                    moon_cells = [
                        ("",            Qt.AlignmentFlag.AlignLeft),
                        (f"↳ m{mi}", Qt.AlignmentFlag.AlignRight),
                        ("",            Qt.AlignmentFlag.AlignLeft),
                        (moon_type,     Qt.AlignmentFlag.AlignLeft),
                        (moon_profile,  Qt.AlignmentFlag.AlignLeft),
                        (moon_codes,    Qt.AlignmentFlag.AlignLeft),
                        ("",            Qt.AlignmentFlag.AlignLeft),
                        ("",            Qt.AlignmentFlag.AlignLeft),
                    ]
                    for col, (text, align) in enumerate(moon_cells):
                        lbl = QLabel(text)
                        lbl.setObjectName("table-moon")
                        lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                        grid.addWidget(lbl, grid_row, col)
                    grid_row += 1

        return group

    def _build_world_card(self, world: object) -> QWidget:
        w = world
        d = w.to_dict()  # type: ignore[attr-defined]

        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(self._build_stat_row(w, d))
        layout.addWidget(self._build_detail_cards(w, d))
        layout.addWidget(self._build_trade_codes(w))
        notes = self._build_notes(w)
        if notes:
            layout.addWidget(notes)
        layout.addStretch()
        return card

    def _build_stat_row(self, w: object, d: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        def stat_group(title: str, value: str, subtitle: str) -> QGroupBox:
            group = QGroupBox(title)
            inner = QVBoxLayout(group)
            inner.setSpacing(2)
            inner.setContentsMargins(8, 4, 8, 6)
            v = QLabel(value)
            v.setObjectName("stat-value")
            v.setAlignment(Qt.AlignmentFlag.AlignLeft)
            v.setWordWrap(True)
            s = QLabel(subtitle)
            s.setObjectName("stat-sub")
            s.setAlignment(Qt.AlignmentFlag.AlignLeft)
            s.setWordWrap(True)
            inner.addWidget(v)
            inner.addWidget(s)
            return group

        sp = w.starport  # type: ignore[attr-defined]
        layout.addWidget(
            stat_group(
                "Starport",
                f"{sp} — {STARPORT_QUALITY_LABEL.get(sp, '?')}",
                STARPORT_FACILITY_DETAIL.get(sp, ""),
            ),
            stretch=1,
        )
        layout.addWidget(
            stat_group(
                "Size",
                f"{_to_hex(w.size)} — {d['size']['diameter_km']} km",  # type: ignore[attr-defined]
                f"Gravity: {d['size']['surface_gravity']}",
            ),
            stretch=1,
        )
        layout.addWidget(
            stat_group(
                "Tech Level",
                _to_hex(w.tech_level),  # type: ignore[attr-defined]
                _tl_era(w.tech_level),  # type: ignore[attr-defined]
            ),
            stretch=1,
        )
        return row

    def _build_detail_cards(self, w: object, d: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        phys = QGroupBox("Physical")
        phys.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        pb = QVBoxLayout(phys)
        pb.setSpacing(0)
        pb.setContentsMargins(8, 4, 8, 6)
        gear = d["atmosphere"]["survival_gear"]
        gear_danger = gear not in ("None", "Varies")
        for lbl_text, val_text, danger in [
            ("Atmosphere",      f"{_to_hex(w.atmosphere)} — {d['atmosphere']['name']}", False),  # type: ignore[attr-defined]
            ("Survival gear",   gear,                                                          gear_danger),
            ("Temperature",     w.temperature,                                                 False),   # type: ignore[attr-defined]
            ("Hydrographics",   f"{_to_hex(w.hydrographics)} — {d['hydrographics']['description'].split(' (')[0]}", False),  # type: ignore[attr-defined]
            ("Gas giants",      str(w.gas_giant_count) if w.has_gas_giant else "None",        False),   # type: ignore[attr-defined]
            ("Planetoid belts", str(w.belt_count),                                             False),   # type: ignore[attr-defined]
            ("PBG",             f"{w.population_multiplier}{w.belt_count}{w.gas_giant_count}", False),   # type: ignore[attr-defined]
        ]:
            pb.addWidget(_detail_row(lbl_text, val_text, danger))
        layout.addWidget(phys)

        soc = QGroupBox("Society")
        soc.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        sb = QVBoxLayout(soc)
        sb.setSpacing(0)
        sb.setContentsMargins(8, 4, 8, 6)
        pop_str = f"{_to_hex(w.population)} — {d['population']['range']}"  # type: ignore[attr-defined]
        if w.population > 0:  # type: ignore[attr-defined]
            pop_str += f"  (P={w.population_multiplier})"  # type: ignore[attr-defined]
        bases_str = "  ".join(_BASE_FULL.get(b, b) for b in w.bases) or "None"  # type: ignore[attr-defined]
        for lbl_text, val_text in [
            ("Population", pop_str),
            ("Government", f"{_to_hex(w.government)} — {d['government']['name']}"),  # type: ignore[attr-defined]
            ("Law level",  _to_hex(w.law_level)),  # type: ignore[attr-defined]
            ("Bases",      bases_str),
        ]:
            sb.addWidget(_detail_row(lbl_text, val_text))
        layout.addWidget(soc)

        return row

    def _build_trade_codes(self, w: object) -> QWidget:
        box = QWidget()
        vbox = QVBoxLayout(box)
        vbox.setSpacing(4)
        vbox.setContentsMargins(0, 0, 0, 0)

        hdr = QLabel("Trade codes")
        hdr.setObjectName("section-label")
        vbox.addWidget(hdr)

        badge_row = QWidget()
        hbox = QHBoxLayout(badge_row)
        hbox.setSpacing(4)
        hbox.setContentsMargins(0, 0, 0, 0)

        if w.trade_codes:  # type: ignore[attr-defined]
            for tc in w.trade_codes:  # type: ignore[attr-defined]
                badge = QLabel(f"{tc} — {_TRADE_CODE_FULL.get(tc, tc)}")
                badge.setObjectName("tc-badge")
                hbox.addWidget(badge)
        else:
            none_lbl = QLabel("None")
            none_lbl.setObjectName("dim-label")
            hbox.addWidget(none_lbl)
        hbox.addStretch()

        vbox.addWidget(badge_row)
        return box

    def _build_notes(self, w: object) -> "QGroupBox | None":
        if not w.notes:  # type: ignore[attr-defined]
            return None
        group = QGroupBox("Notes")
        inner = QVBoxLayout(group)
        inner.setSpacing(2)
        inner.setContentsMargins(8, 4, 8, 6)
        for note in w.notes:  # type: ignore[attr-defined]
            lbl = QLabel(f"• {note}")
            lbl.setObjectName("stat-sub")
            lbl.setWordWrap(True)
            inner.addWidget(lbl)
        return group


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Traveller World Generator")
    window = AppWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
