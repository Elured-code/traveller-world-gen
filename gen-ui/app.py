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

import html as _html_mod
import json
import os
import pathlib
import random
import re
import secrets
import sys

from PySide6.QtCore import Qt, QMarginsF, QSettings, QThread, Signal  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QAction, QFontDatabase, QKeySequence, QPageLayout, QPageSize, QShortcut,
)
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
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from traveller_gen.system_map import build_svg, PALETTE_DARK, PALETTE_LIGHT  # noqa: E402


from traveller_gen.traveller_map_fetch import (  # noqa: E402
    AmbiguousWorldError, generate_system_from_map,
)
from traveller_gen.traveller_system_gen import generate_full_system, TravellerSystem  # noqa: E402
from traveller_gen.traveller_world_gen import (  # noqa: E402
    World,
    generate_atmosphere_detail,
    generate_gas_mix,
    generate_unusual_subtype,
    generate_world,
)
from traveller_gen.tables import ZONE_CSS_CLASS  # noqa: E402
from traveller_gen.traveller_hydro_detail import generate_hydrographic_detail  # noqa: E402
from traveller_gen.system_pipeline import PipelineOptions, run_detail_pipeline  # noqa: E402
from traveller_gen.world_codes import APP_VERSION  # noqa: E402

try:
    from traveller_gen import _version as _gen_ver  # type: ignore[import]  # noqa: E402
    _DISPLAY_VERSION = _gen_ver.__version__
except ImportError:
    _DISPLAY_VERSION = APP_VERSION

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_USER_GUIDE_PATH = _REPO_ROOT / "docs" / "Traveller World Generator User Guide.md"

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
QFrame#onboard-card { border: 1px solid #cccccc; border-radius: 8px; }
QLabel#version-label { font-size: 9pt; color: #888888; }
"""

_CSS_DARK = """
QWidget { background-color: #1e1e1e; color: #e0e0e0; }
QLabel#zone-green   { background-color: #27ae60; color: white;
                      padding: 2px 10px; border-radius: 4px; }
QLabel#zone-amber   { background-color: #e67e22; color: white;
                      padding: 2px 10px; border-radius: 4px; }
QLabel#zone-red     { background-color: #c0392b; color: white;
                      padding: 2px 10px; border-radius: 4px; }
QLabel#uwp-label    { font-family: monospace; font-size: 18pt; font-weight: bold; }
QLabel#world-name   { font-size: 16pt; font-weight: bold; }
QLabel#error-label  { color: #ff6b6b; font-weight: bold; }
QLabel#hint-label   { font-style: italic; }
QLabel#dim-label    { color: #aaaaaa; }
QLabel#stat-value   { font-size: 13pt; font-weight: bold; }
QLabel#stat-sub     { font-size: 9pt; }
QLabel#section-label { font-size: 9pt; font-weight: bold; }
QLabel#row-label    { font-size: 10pt; }
QLabel#row-value    { font-size: 10pt; font-weight: bold; }
QLabel#danger-value { font-size: 10pt; font-weight: bold; color: #ff6b6b; }
QLabel#tc-badge     { background-color: #3d1f17; color: #f5a78a;
                      padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
QLabel#table-header { font-size: 9pt; font-weight: bold; }
QLabel#table-cell   { font-size: 10pt; color: #e0e0e0; }
QLabel#table-mw     { font-size: 10pt; font-weight: bold; }
QLabel#table-dim    { font-size: 10pt; color: #6b7280; }
QLabel#table-moon   { font-size: 9pt; color: #aaaaaa; }
QPushButton#suggested-action { background-color: #3584e4; color: white; }
QFrame#onboard-card { border: 1px solid #444444; border-radius: 8px; }
"""

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
# Markdown renderer
# ---------------------------------------------------------------------------


def _md_to_html(md: str, dark: bool = False) -> str:  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    """Convert a subset of Markdown to a styled standalone HTML document."""

    def _inline(text: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        return text

    def _is_sep(s: str) -> bool:
        return bool(re.match(r'^\|[\s:|-]+\|$', s.strip()))

    def _row_cells(s: str) -> list[str]:
        return [_inline(_html_mod.escape(c.strip())) for c in s.split('|')[1:-1]]

    bg       = "#1e1e1e" if dark else "#ffffff"
    fg       = "#e0e0e0" if dark else "#1a1a1a"
    code_bg  = "#2d2d2d" if dark else "#f4f4f4"
    link_col = "#64b5f6" if dark else "#1565c0"
    border   = "#444444" if dark else "#cccccc"
    th_bg    = "#2d2d2d" if dark else "#f0f0f0"

    parts: list[str] = []
    in_code = False
    in_ul   = False
    in_ol   = False
    in_table = False
    pending_header: list[str] | None = None
    para:   list[str] = []

    def flush_para() -> None:
        if para:
            parts.append(f'<p>{_inline(" ".join(para))}</p>')
            para.clear()

    def close_list() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            parts.append('</ul>')
            in_ul = False
        if in_ol:
            parts.append('</ol>')
            in_ol = False

    def close_table() -> None:
        nonlocal in_table, pending_header
        if in_table:
            parts.append('</tbody></table>')
            in_table = False
        pending_header = None

    for raw in md.split('\n'):
        line = raw.rstrip()

        # ── fenced code block ──────────────────────────────────────────
        if line.startswith('```'):
            if in_code:
                parts.append('</code></pre>')
                in_code = False
            else:
                flush_para()
                close_list()
                close_table()
                parts.append('<pre><code>')
                in_code = True
            continue

        if in_code:
            parts.append(_html_mod.escape(raw))
            continue

        # ── blank line ─────────────────────────────────────────────────
        if not line:
            flush_para()
            close_list()
            close_table()
            continue

        # ── table row or separator ─────────────────────────────────────
        if line.startswith('|'):
            if _is_sep(line):
                if pending_header is not None:
                    cells_html = ''.join(f'<th>{c}</th>' for c in pending_header)
                    parts.append(
                        f'<table><thead><tr>{cells_html}</tr></thead><tbody>'
                    )
                    in_table = True
                    pending_header = None
            elif in_table:
                row_html = ''.join(f'<td>{c}</td>' for c in _row_cells(line))
                parts.append(f'<tr>{row_html}</tr>')
            else:
                flush_para()
                close_list()
                pending_header = _row_cells(line)
            continue

        # ── non-pipe line: close open table ────────────────────────────
        if in_table or pending_header is not None:
            close_table()

        # ── ATX heading ────────────────────────────────────────────────
        m = re.match(r'^(#{1,6}) (.*)', line)
        if m:
            flush_para()
            close_list()
            n = len(m.group(1))
            parts.append(f'<h{n}>{_inline(_html_mod.escape(m.group(2)))}</h{n}>')
            continue

        # ── horizontal rule ────────────────────────────────────────────
        if re.match(r'^---+\s*$', line):
            flush_para()
            close_list()
            parts.append('<hr>')
            continue

        # ── unordered list ─────────────────────────────────────────────
        m = re.match(r'^[-*] (.*)', line)
        if m:
            flush_para()
            if in_ol:
                parts.append('</ol>')
                in_ol = False
            if not in_ul:
                parts.append('<ul>')
                in_ul = True
            parts.append(f'<li>{_inline(_html_mod.escape(m.group(1)))}</li>')
            continue

        # ── ordered list ───────────────────────────────────────────────
        m = re.match(r'^\d+\. (.*)', line)
        if m:
            flush_para()
            if in_ul:
                parts.append('</ul>')
                in_ul = False
            if not in_ol:
                parts.append('<ol>')
                in_ol = True
            parts.append(f'<li>{_inline(_html_mod.escape(m.group(1)))}</li>')
            continue

        # ── paragraph text ─────────────────────────────────────────────
        para.append(_html_mod.escape(line))

    flush_para()
    close_list()
    close_table()
    if in_code:
        parts.append('</code></pre>')

    body = '\n'.join(parts)
    css = (
        f'body{{font-family:sans-serif;font-size:14px;max-width:860px;'
        f'margin:0 auto;padding:20px 32px;background:{bg};color:{fg};line-height:1.6}}'
        f'h1{{font-size:1.6em;border-bottom:2px solid {border};padding-bottom:6px;margin-top:0}}'
        f'h2{{font-size:1.3em;border-bottom:1px solid {border};'
        f'padding-bottom:4px;margin-top:1.6em}}'
        f'h3{{font-size:1.1em;margin-top:1.4em}}'
        f'pre{{background:{code_bg};padding:12px;border-radius:4px;overflow-x:auto;font-size:12px}}'
        f'code{{font-family:monospace;background:{code_bg};padding:1px 4px;border-radius:3px}}'
        f'pre code{{background:none;padding:0}}'
        f'a{{color:{link_col}}}'
        f'hr{{border:none;border-top:1px solid {border};margin:20px 0}}'
        f'ul,ol{{padding-left:1.5em}}'
        f'li{{margin:4px 0}}'
        f'table{{border-collapse:collapse;width:100%;margin:12px 0}}'
        f'th{{background:{th_bg};text-align:left;padding:6px 10px;'
        f'border:1px solid {border};font-weight:bold}}'
        f'td{{padding:6px 10px;border:1px solid {border};vertical-align:top}}'
    )
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<style>{css}</style></head><body>{body}</body></html>'
    )


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

        _s = QSettings("traveller-world-gen", "AppWindow")
        is_light = str(_s.value("map_light_theme", False)).lower() == "true"
        self._system = system
        self._palette = PALETTE_LIGHT if is_light else PALETTE_DARK
        self._perspective = str(_s.value("map_perspective", False)).lower() == "true"
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

        self._theme_btn = QPushButton("Dark Theme" if is_light else "Light Theme")
        self._theme_btn.clicked.connect(self._toggle_theme)
        tbox.addWidget(self._theme_btn)

        self._persp_btn = QPushButton(
            "Top-down View" if self._perspective else "Perspective View"
        )
        self._persp_btn.clicked.connect(self._toggle_perspective)
        tbox.addWidget(self._persp_btn)

        save_btn = QPushButton("Save SVG…")
        save_btn.clicked.connect(self._on_save)
        tbox.addWidget(save_btn)
        tbox.addStretch()
        vbox.addWidget(toolbar)
        vbox.addWidget(_make_hsep())

        # QWebEngineView (Chromium) handles the full SVG feature set including
        # feGaussianBlur filters and correct palette background colours.
        self._map_view = QWebEngineView()
        vbox.addWidget(self._map_view, stretch=1)

        self._render()

    def _render(self) -> None:
        svg_str, _canvas_h = build_svg(
            self._system, canvas_w=_MAP_CANVAS_W,
            palette=self._palette, perspective=self._perspective,
        )
        self._svg_str = svg_str
        bg = self._palette.bg
        html = (
            f'<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<style>html,body{{margin:0;padding:0;background:{bg};}}</style>'
            f'</head><body>{svg_str}</body></html>'
        )
        self._map_view.setHtml(html)

    def _toggle_theme(self) -> None:
        if self._palette is PALETTE_DARK:
            self._palette = PALETTE_LIGHT
            self._theme_btn.setText("Dark Theme")
        else:
            self._palette = PALETTE_DARK
            self._theme_btn.setText("Light Theme")
        QSettings("traveller-world-gen", "AppWindow").setValue(
            "map_light_theme", self._palette is PALETTE_LIGHT
        )
        self._render()

    def _toggle_perspective(self) -> None:
        self._perspective = not self._perspective
        self._persp_btn.setText(
            "Top-down View" if self._perspective else "Perspective View"
        )
        QSettings("traveller-world-gen", "AppWindow").setValue(
            "map_perspective", self._perspective
        )
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


class SurveyFormWindow(QMainWindow):  # pylint: disable=too-few-public-methods
    """Non-modal window that displays an IISS survey form for the system."""

    def __init__(self, title: str, html: str) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.resize(980, 700)

        self._view = QWebEngineView()
        self.setCentralWidget(self._view)
        self._view.setHtml(html)


class UserGuideWindow(QMainWindow):  # pylint: disable=too-few-public-methods
    """Non-modal window that displays the rendered User Guide."""

    def __init__(self, md_path: pathlib.Path, dark: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("User Guide — Traveller World Generator")
        self.resize(900, 720)
        view = QWebEngineView()
        self.setCentralWidget(view)
        try:
            html = _md_to_html(md_path.read_text(encoding="utf-8"), dark=dark)
        except OSError as exc:
            html = f"<p>Could not load user guide: {_html_mod.escape(str(exc))}</p>"
        view.setHtml(html)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------


class _TravMapWorker(QThread):  # pylint: disable=too-few-public-methods
    """Background thread for TravellerMap network lookups."""

    result = Signal(object)     # system object on success
    failed = Signal(str)        # error message string
    ambiguous = Signal(object)  # AmbiguousWorldError instance

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        sector: str,
        search_name: "str | None",
        hex_pos: "str | None",
        seed: int,
        orbital_eccentricity: bool = True,
        orbital_inclination: bool = True,
    ) -> None:
        super().__init__()
        self._sector = sector
        self._search_name = search_name
        self._hex_pos = hex_pos
        self._seed = seed
        self._orbital_eccentricity = orbital_eccentricity
        self._orbital_inclination = orbital_inclination

    def run(self) -> None:
        """Call generate_system_from_map and emit result, failed, or ambiguous."""
        try:
            system = generate_system_from_map(
                name=self._search_name,
                sector=self._sector,
                hex_pos=self._hex_pos,
                seed=self._seed,
                orbital_eccentricity=self._orbital_eccentricity,
                orbital_inclination=self._orbital_inclination,
            )
            self.result.emit(system)
        except AmbiguousWorldError as exc:
            self.ambiguous.emit(exc)
        except (ValueError, LookupError, ConnectionError) as exc:
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Options dialog
# ---------------------------------------------------------------------------


class _OptionsDialog(QDialog):
    """Modal dialog for configuring generation options."""
    # pylint: disable=missing-function-docstring,too-many-instance-attributes

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-statements,too-many-locals
        self,
        parent: QWidget,
        *,
        full_system: bool,
        nhz: bool,
        oxygen_biomass: bool,
        runaway_greenhouse: bool,
        independent_government: bool,
        select_mainworld: bool,
        social_detail: bool,
        settlement_type: str,
        eccentricity: bool = True,
        inclination: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generation Options")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._check_system = QCheckBox("System detail")
        self._check_system.setChecked(full_system)
        layout.addWidget(self._check_system)

        self._sub_widget = QWidget()
        checks_layout = QVBoxLayout(self._sub_widget)
        checks_layout.setSpacing(6)
        checks_layout.setContentsMargins(20, 0, 0, 0)
        self._check_nhz = QCheckBox("NHZ Atmospheres")
        self._check_nhz.setChecked(nhz)
        self._check_oxygen_biomass = QCheckBox("Oxygen requires biomass")
        self._check_oxygen_biomass.setChecked(oxygen_biomass)
        self._check_runaway_greenhouse = QCheckBox("Runaway greenhouse")
        self._check_runaway_greenhouse.setChecked(runaway_greenhouse)
        self._check_eccentricity = QCheckBox("Orbital eccentricity")
        self._check_eccentricity.setChecked(eccentricity)
        self._check_inclination = QCheckBox("Orbital inclination")
        self._check_inclination.setChecked(inclination)
        self._check_independent_gov = QCheckBox("Independent government")
        self._check_independent_gov.setChecked(independent_government)
        self._check_select_mw = QCheckBox("Select mainworld")
        self._check_select_mw.setChecked(select_mainworld)
        checks_layout.addWidget(self._check_nhz)
        checks_layout.addWidget(self._check_oxygen_biomass)
        checks_layout.addWidget(self._check_runaway_greenhouse)
        checks_layout.addWidget(self._check_eccentricity)
        checks_layout.addWidget(self._check_inclination)
        checks_layout.addWidget(self._check_independent_gov)
        checks_layout.addWidget(self._check_select_mw)
        layout.addWidget(self._sub_widget)

        self._check_social_detail = QCheckBox("Social detail")
        self._check_social_detail.setChecked(social_detail)
        layout.addWidget(self._check_social_detail)

        settlement_group = QGroupBox("Settlement type")
        settlement_layout = QVBoxLayout(settlement_group)
        settlement_layout.setSpacing(4)
        self._settlement_btn_group = QButtonGroup(self)
        for label, key in (
            ("Standard", "standard"),
            ("Long-settled", "long_settled"),
            ("Well-settled", "well_settled"),
            ("Backwater", "backwater"),
            ("Unsettled", "unsettled"),
        ):
            btn = QRadioButton(label)
            btn.setProperty("key", key)
            self._settlement_btn_group.addButton(btn)
            settlement_layout.addWidget(btn)
            if key == settlement_type:
                btn.setChecked(True)
        if self._settlement_btn_group.checkedButton() is None:
            self._settlement_btn_group.buttons()[0].setChecked(True)
        layout.addWidget(settlement_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._check_system.toggled.connect(self._on_group_toggled)
        self._on_group_toggled(full_system)

    def _on_group_toggled(self, checked: bool) -> None:
        self._sub_widget.setVisible(checked)
        if not checked:
            for cb in (
                self._check_nhz, self._check_oxygen_biomass,
                self._check_runaway_greenhouse,
                self._check_eccentricity, self._check_inclination,
                self._check_independent_gov, self._check_select_mw,
            ):
                cb.setChecked(False)

    @property
    def full_system(self) -> bool:
        return self._check_system.isChecked()

    @property
    def nhz(self) -> bool:
        return self._check_nhz.isChecked()

    @property
    def oxygen_biomass(self) -> bool:
        return self._check_oxygen_biomass.isChecked()

    @property
    def runaway_greenhouse(self) -> bool:
        return self._check_runaway_greenhouse.isChecked()

    @property
    def eccentricity(self) -> bool:
        return self._check_eccentricity.isChecked()

    @property
    def inclination(self) -> bool:
        return self._check_inclination.isChecked()

    @property
    def independent_government(self) -> bool:
        return self._check_independent_gov.isChecked()

    @property
    def select_mainworld(self) -> bool:
        return self._check_select_mw.isChecked()

    @property
    def social_detail(self) -> bool:
        return self._check_social_detail.isChecked()

    @property
    def settlement_type(self) -> str:
        btn = self._settlement_btn_group.checkedButton()
        return btn.property("key") if btn is not None else "none"


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class AppWindow(QMainWindow):  # pylint: disable=too-few-public-methods,too-many-instance-attributes,attribute-defined-outside-init
    """Main application window for the Traveller World Generator."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Traveller World Generator {_DISPLAY_VERSION}")
        self.resize(1100, 700)
        self.setMinimumSize(780, 500)
        self._current_world: object | None = None
        self._current_system: object | None = None
        self._detail_attached: bool = False
        self._seed_auto: bool = False
        self._map_windows: list[object] = []
        self._survey_windows: list[object] = []
        self._poster_pdf_exports: list[object] = []
        self._user_guide_windows: list[object] = []
        self._map_btn: QPushButton | None = None
        self._survey_btn: QPushButton | None = None
        self._survey_combo: QComboBox | None = None
        self._generate_btn: QPushButton | None = None
        self._worker: _TravMapWorker | None = None
        self._pending_full_system: bool = False
        self._pending_attach_detail: bool = False
        self._pending_seed: int = 0
        self._pending_rng: random.Random | None = None
        _s = QSettings("traveller-world-gen", "AppWindow")
        raw = _s.value("dark_mode", False)
        self._dark_mode: bool = str(raw).lower() == "true"
        self._opt_full_system: bool = str(_s.value("opt_full_system", False)).lower() == "true"
        self._opt_nhz: bool = str(_s.value("opt_nhz", False)).lower() == "true"
        self._opt_oxygen_biomass: bool = (
            str(_s.value("opt_oxygen_biomass", False)).lower() == "true"
        )
        self._opt_runaway_greenhouse: bool = (
            str(_s.value("opt_runaway_greenhouse", False)).lower() == "true"
        )
        self._opt_independent_gov: bool = (
            str(_s.value("opt_independent_gov", False)).lower() == "true"
        )
        self._opt_social_detail: bool = (
            str(_s.value("opt_social_detail", False)).lower() == "true"
        )
        self._opt_select_mw: bool = (
            str(_s.value("opt_select_mw", False)).lower() == "true"
        )
        self._opt_eccentricity: bool = (
            str(_s.value("opt_eccentricity", True)).lower() != "false"
        )
        self._opt_inclination: bool = (
            str(_s.value("opt_inclination", True)).lower() != "false"
        )
        self._opt_settlement_type: str = str(_s.value("opt_settlement_type", "standard"))
        self._apply_theme()
        self._build_menu_bar()
        self._build_ui()
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Quit, self).activated.connect(
            QApplication.instance().quit  # type: ignore[union-attr]
        )
        QShortcut(QKeySequence.StandardKey.Close, self).activated.connect(self.close)

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
            css = _CSS_DARK if self._dark_mode else _CSS
            app.setStyleSheet(css.replace("font-family: monospace", f'font-family: "{mono}"'))

    def _themed_html(self, html: str) -> str:
        if self._dark_mode:
            return html.replace('<html lang="en">', '<html lang="en" data-theme="dark">', 1)
        return html

    def _on_toggle_dark_mode(self, checked: bool) -> None:
        self._dark_mode = checked
        self._apply_theme()
        QSettings("traveller-world-gen", "AppWindow").setValue("dark_mode", checked)
        if self._current_system is not None:
            self._show_system_summary(self._current_system)
        elif self._current_world is not None:
            self._show_summary(self._current_world)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setMinimumWidth(740)
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

        ver_label = QLabel(_DISPLAY_VERSION)
        ver_label.setObjectName("version-label")
        self.statusBar().addPermanentWidget(ver_label)

        self._show_placeholder()

    def _build_controls(self) -> QWidget:
        # pylint: disable=attribute-defined-outside-init
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setSpacing(4)
        vbox.setContentsMargins(0, 0, 0, 0)

        # ── Row 1: Name + Generate ──────────────────────────────────
        row1 = QWidget()
        r1 = QHBoxLayout(row1)
        r1.setSpacing(8)
        r1.setContentsMargins(0, 0, 0, 0)

        r1.addWidget(QLabel("Name:"))
        self._name_entry = QLineEdit()
        self._name_entry.setPlaceholderText("World name (optional)")
        self._name_entry.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._name_entry.returnPressed.connect(self._on_generate)
        r1.addWidget(self._name_entry)

        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setObjectName("suggested-action")
        self._generate_btn.clicked.connect(self._on_generate)
        r1.addWidget(self._generate_btn)

        vbox.addWidget(row1)

        # ── Row 2: Seed (secondary) ─────────────────────────────────
        row2 = QWidget()
        r2 = QHBoxLayout(row2)
        r2.setSpacing(8)
        r2.setContentsMargins(0, 0, 0, 0)

        r2.addWidget(QLabel("Seed:"))
        self._seed_entry = QLineEdit()
        self._seed_entry.setPlaceholderText("Integer (optional)")
        self._seed_entry.setFixedWidth(140)
        self._seed_entry.returnPressed.connect(self._on_generate)
        self._seed_entry.textChanged.connect(lambda _: self._on_seed_changed())
        r2.addWidget(self._seed_entry)

        clear_btn = QPushButton("New Seed")
        clear_btn.clicked.connect(self._on_clear_seed)
        r2.addWidget(clear_btn)

        r2.addStretch()

        vbox.addWidget(row2)

        return container

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

        options_btn = QPushButton("Options…")
        options_btn.clicked.connect(self._on_options_clicked)
        left_layout.addWidget(options_btn)

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
        if self._map_btn is not None:
            self._map_btn.setEnabled(checked)

    def _on_source_toggled(self, checked: bool) -> None:  # pylint: disable=unused-argument
        procedural = self._radio_procedural.isChecked()
        self._tm_panel.setVisible(not procedural)
        self._tm_vsep.setVisible(not procedural)

    def _on_options_clicked(self) -> None:
        dialog = _OptionsDialog(
            self,
            full_system=self._opt_full_system,
            nhz=self._opt_nhz,
            oxygen_biomass=self._opt_oxygen_biomass,
            runaway_greenhouse=self._opt_runaway_greenhouse,
            independent_government=self._opt_independent_gov,
            select_mainworld=self._opt_select_mw,
            social_detail=self._opt_social_detail,
            settlement_type=self._opt_settlement_type,
            eccentricity=self._opt_eccentricity,
            inclination=self._opt_inclination,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._opt_full_system = dialog.full_system
        self._opt_nhz = dialog.nhz
        self._opt_oxygen_biomass = dialog.oxygen_biomass
        self._opt_runaway_greenhouse = dialog.runaway_greenhouse
        self._opt_independent_gov = dialog.independent_government
        self._opt_select_mw = dialog.select_mainworld
        self._opt_social_detail = dialog.social_detail
        self._opt_settlement_type = dialog.settlement_type
        self._opt_eccentricity = dialog.eccentricity
        self._opt_inclination = dialog.inclination
        _s = QSettings("traveller-world-gen", "AppWindow")
        _s.setValue("opt_full_system", self._opt_full_system)
        _s.setValue("opt_nhz", self._opt_nhz)
        _s.setValue("opt_oxygen_biomass", self._opt_oxygen_biomass)
        _s.setValue("opt_runaway_greenhouse", self._opt_runaway_greenhouse)
        _s.setValue("opt_independent_gov", self._opt_independent_gov)
        _s.setValue("opt_select_mw", self._opt_select_mw)
        _s.setValue("opt_social_detail", self._opt_social_detail)
        _s.setValue("opt_settlement_type", self._opt_settlement_type)
        _s.setValue("opt_eccentricity", self._opt_eccentricity)
        _s.setValue("opt_inclination", self._opt_inclination)
        self._on_detail_toggled(self._opt_full_system)

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

        full_system = self._opt_full_system
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
            self._pending_full_system = full_system
            self._pending_attach_detail = attach_detail_flag
            self._pending_seed = seed
            self._pending_rng = None
            self._start_travellermap_worker(
                sector, search_name, hex_pos, seed,
                orbital_eccentricity=self._opt_eccentricity,
                orbital_inclination=self._opt_inclination,
            )
        else:
            if full_system:
                rng = random.Random(seed)
                system = generate_full_system(
                    name, seed=seed, rng=rng,
                    nhz_atmospheres=self._opt_nhz,
                    orbital_eccentricity=self._opt_eccentricity,
                    orbital_inclination=self._opt_inclination,
                )
                self._finish_system_generation(system, attach_detail_flag, rng=rng)
            else:
                world = generate_world(
                    name, settlement_type=self._opt_settlement_type,
                )
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
        if self._opt_social_detail:
            from traveller_world_population_detail import generate_population_detail  # pylint: disable=import-outside-toplevel
            from traveller_world_government_detail import generate_government_detail  # pylint: disable=import-outside-toplevel
            from traveller_world_law_detail import generate_law_detail  # pylint: disable=import-outside-toplevel
            if world.population > 0:  # type: ignore[attr-defined]
                world.population_detail = generate_population_detail(  # type: ignore[attr-defined]
                    world.population, world.population_multiplier,  # type: ignore[attr-defined]
                    size=world.size, tl=world.tech_level,  # type: ignore[attr-defined]
                    government=world.government,  # type: ignore[attr-defined]
                    law_level=world.law_level,  # type: ignore[attr-defined]
                    trade_codes=world.trade_codes,  # type: ignore[attr-defined]
                    atm=world.atmosphere,  # type: ignore[attr-defined]
                )
                pop_det = world.population_detail  # type: ignore[attr-defined]
                pcr = pop_det.pcr if pop_det is not None else 0
                world.government_detail = generate_government_detail(  # type: ignore[attr-defined]
                    world.government, world.population, pcr=pcr,  # type: ignore[attr-defined]
                )
                gov_auth = (
                    world.government_detail.authority_code  # type: ignore[attr-defined]
                    if world.government_detail is not None else ""  # type: ignore[attr-defined]
                )
                world.law_detail = generate_law_detail(  # type: ignore[attr-defined]
                    world.law_level, world.government,  # type: ignore[attr-defined]
                    world.tech_level, pcr=pcr,  # type: ignore[attr-defined]
                    gov_authority_code=gov_auth,
                )
                from traveller_world_tech_detail import generate_tech_detail  # pylint: disable=import-outside-toplevel
                world.tech_detail = generate_tech_detail(  # type: ignore[attr-defined]
                    world.tech_level, world.atmosphere,  # type: ignore[attr-defined]
                    world.hydrographics, world.population,  # type: ignore[attr-defined]
                    world.government, world.law_level,  # type: ignore[attr-defined]
                    world.starport, pcr=pcr,  # type: ignore[attr-defined]
                )
                cx: str = getattr(world, "cx", "")
                if cx:
                    from traveller_world_culture_detail import (  # pylint: disable=import-outside-toplevel
                        generate_culture_detail_from_cx,
                    )
                    world.culture_detail = (  # type: ignore[attr-defined]
                        generate_culture_detail_from_cx(
                            cx=cx,
                            population=world.population,  # type: ignore[attr-defined]
                            importance=getattr(world, "importance", 0),
                            government=world.government,  # type: ignore[attr-defined]
                            law_level=world.law_level,  # type: ignore[attr-defined]
                            pcr=pcr,
                            starport=world.starport,  # type: ignore[attr-defined]
                            tech_level=world.tech_level,  # type: ignore[attr-defined]
                        )
                    )
                else:
                    from traveller_world_culture_detail import generate_culture_detail  # pylint: disable=import-outside-toplevel
                    world.culture_detail = generate_culture_detail(  # type: ignore[attr-defined]
                        world.population, world.government,  # type: ignore[attr-defined]
                        world.law_level, pcr=pcr,  # type: ignore[attr-defined]
                        starport=world.starport,  # type: ignore[attr-defined]
                        tech_level=world.tech_level,  # type: ignore[attr-defined]
                    )
        self._act_save.setEnabled(True)
        self._act_export_poster.setEnabled(False)
        self._show_summary(world)

    def _finish_system_generation(
        self, system: object, attach_detail_flag: bool = False,
        rng: random.Random | None = None,
    ) -> None:
        self._current_system = system
        run_detail_pipeline(  # type: ignore[arg-type]
            system, rng,  # type: ignore[arg-type]
            PipelineOptions(
                want_detail=attach_detail_flag,
                want_select_mw=self._opt_select_mw and attach_detail_flag,
                runaway_greenhouse=self._opt_runaway_greenhouse,
                independent_government=self._opt_independent_gov,
                optional_biomass=self._opt_oxygen_biomass,
                settlement_type=self._opt_settlement_type,
                want_social_detail=self._opt_social_detail,
            ),
        )
        self._current_world = system.mainworld  # type: ignore[attr-defined]
        self._detail_attached = attach_detail_flag
        self._act_save.setEnabled(True)
        self._act_export_poster.setEnabled(self._current_world is not None)
        self._show_system_summary(system)

    def _load_system_from_json(self, system: object) -> None:
        self._current_system = system
        self._current_world = system.mainworld  # type: ignore[attr-defined]
        self._detail_attached = False
        self._act_save.setEnabled(True)
        self._act_export_poster.setEnabled(self._current_world is not None)
        self._show_system_summary(system)
        if self._map_btn is not None:
            self._map_btn.setEnabled(True)

    def _show_disambiguation_dialog(  # pylint: disable=too-many-locals
        self,
        error: AmbiguousWorldError,
        seed: int,
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
                self._start_travellermap_worker(
                    error.sector, None, selected, seed,
                    orbital_eccentricity=self._opt_eccentricity,
                    orbital_inclination=self._opt_inclination,
                )

    def _on_map_clicked(self) -> None:
        if self._current_system is None:
            return
        win = SystemMapWindow(self._current_system)
        self._map_windows.append(win)
        win.show()

    def _on_survey_clicked(self) -> None:
        if self._current_system is None:
            return
        form_type = (
            self._survey_combo.currentText()
            if self._survey_combo is not None
            else "Class 0/I Survey"
        )
        system = self._current_system  # type: ignore[attr-defined]
        mw = system.mainworld
        name = mw.name if mw else "System"
        if form_type == "Class II/III Survey":
            html_raw = system.to_survey_form_html_class2()
        elif form_type == "Class IV Survey":
            html_raw = system.to_survey_form_html_class4()
        else:
            html_raw = system.to_survey_form_html()
        html = self._themed_html(html_raw)
        win = SurveyFormWindow(f"{form_type} — {name}", html)
        self._survey_windows.append(win)
        win.show()

    def _build_menu_bar(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        file_menu = self.menuBar().addMenu("&File")

        self._act_open_json = QAction("Open JSON…", self)
        self._act_open_json.triggered.connect(self._on_open_json)
        file_menu.addAction(self._act_open_json)

        file_menu.addSeparator()

        self._act_save = QAction("Save As…", self)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save.setEnabled(False)
        self._act_save.triggered.connect(self._on_save_clicked)
        file_menu.addAction(self._act_save)

        self._act_export_poster = QAction("Export A3 Poster…", self)
        self._act_export_poster.setEnabled(False)
        self._act_export_poster.triggered.connect(self._on_export_poster_clicked)
        file_menu.addAction(self._act_export_poster)

        view_menu = self.menuBar().addMenu("&View")
        self._act_dark_mode = QAction("Dark Mode", self)
        self._act_dark_mode.setCheckable(True)
        self._act_dark_mode.setChecked(self._dark_mode)
        self._act_dark_mode.triggered.connect(self._on_toggle_dark_mode)
        view_menu.addAction(self._act_dark_mode)

        help_menu = self.menuBar().addMenu("&Help")
        self._act_user_guide = QAction("User Guide", self)
        self._act_user_guide.triggered.connect(self._on_user_guide)
        help_menu.addAction(self._act_user_guide)
        help_menu.addSeparator()
        self._act_about = QAction("About", self)
        self._act_about.triggered.connect(self._show_about)
        help_menu.addAction(self._act_about)

    def _show_about(self) -> None:
        """Display the About dialog with app info, credits, and license."""
        dlg = QDialog(self)
        dlg.setWindowTitle("About Traveller World & System Generator")
        dlg.setFixedWidth(520)
        dlg.setSizeGripEnabled(False)

        label = QLabel()
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(
            "<h3>Traveller World &amp; System Generator</h3>"
            "<p>A tool for generating star systems, worlds, and survey forms for the "
            "<em>Traveller</em> science-fiction role-playing game, using the rules from the "
            "<em>World Builders' Handbook</em> (Mongoose Publishing).</p>"
            f"<p><b>Version:</b> {_DISPLAY_VERSION}</p>"
            "<p><b>Source code:</b> "
            "<a href='https://github.com/Elured-code/traveller-world-gen'>"
            "github.com/Elured-code/traveller-world-gen</a></p>"
            "<hr>"
            "<p><b>Classic Traveller</b><br>Marc Miller</p>"
            "<p><b>World Builders' Handbook</b> (Mongoose Traveller)<br>"
            "<i>Author:</i> Geir Lanesskog<br>"
            "<i>Developer:</i> Isabella Treccani-Chinelli<br>"
            "<i>Layout &amp; Graphic Design:</i> Sandrine Thirache<br>"
            "<i>Illustrations:</i> Shane Watson, Quentin Soubrouillard, Gary Trow, "
            "Lucas Bonatto Guerrini, Sergio Villa, Mark Graham<br>"
            "<i>Proofing:</i> Charlotte Law</p>"
            "<p><b>Mongoose Traveller Core Rulebook</b><br>"
            "<i>Developer:</i> Matthew Sprange<br>"
            "<i>Original Core Mechanics:</i> Gareth Hanrahan<br>"
            "<i>Layout:</i> Katrina Hepburn, Sandrine Thirache<br>"
            "<i>Illustrations:</i> Xavier Bernard, Sergio Villa, Anderson Maia, "
            "Mark Graham, Nikita Vasylchuk, Douglas Deri, Ian Stead, Ankit Yadav, "
            "Cassie Gregory, Alessandro Rocco<br>"
            "<i>Proofing:</i> Charlotte Law</p>"
            "<p><b>Traveller Inner Circle</b><br>"
            "Andrew James, Alan Welty, Colin Dunn, M. J. Dougherty, Rob Eaglestone, "
            "Sam Wissa, Joshua Bell, Maksim Smelchak, Geir Lanesskog, "
            "Christopher Griffen</p>"
            "<hr>"
            "<p><b>License:</b> MIT License — "
            "<a href='https://opensource.org/licenses/MIT'>opensource.org/licenses/MIT</a></p>"
            "<p><small><i>Traveller</i> is a registered trademark of Far Future Enterprises. "
            "<em>World Builders' Handbook</em> is published by Mongoose Publishing. "
            "This software is an unofficial fan tool and is not affiliated with, endorsed by, "
            "or connected to Mongoose Publishing or Far Future Enterprises. All Traveller game "
            "rules, settings, and concepts remain the intellectual property of their respective "
            "rights holders.</small></p>"
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)

        layout = QVBoxLayout(dlg)
        layout.addWidget(label)
        layout.addWidget(buttons)
        dlg.exec()

    def _on_user_guide(self) -> None:
        win = UserGuideWindow(_USER_GUIDE_PATH, dark=self._dark_mode)
        self._user_guide_windows.append(win)
        win.show()

    def _on_open_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            self._show_error(f"Could not read file: {exc}")
            return

        file_ver = data.get("_app_version")
        def _ver_tuple(v: object) -> tuple:
            try:
                return tuple(int(x) for x in str(v).split("+", maxsplit=1)[0].split("."))
            except (ValueError, AttributeError):
                return ()
        if _ver_tuple(file_ver) != _ver_tuple(APP_VERSION):
            result = QMessageBox.warning(
                self,
                "Version mismatch",
                f"This file was saved with version {file_ver!r}.\n"
                f"Current version is {APP_VERSION!r}.\n"
                "Some fields may be missing or unrecognised. Continue loading?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return

        if "stars" in data:
            try:
                system = TravellerSystem.from_dict(data)
            except (ValueError, KeyError) as exc:
                self._show_error(f"Invalid system JSON: {exc}")
                return
            self._load_system_from_json(system)
            return

        try:
            world = World.from_dict(data)
        except (ValueError, KeyError) as exc:
            self._show_error(f"Invalid world JSON: {exc}")
            return

        self._finish_generation(world)

    def _on_save_clicked(self) -> None:
        obj = self._current_system or self._current_world
        if obj is None:
            return

        base_name = getattr(self._current_world, "name", None) or "world"
        if self._current_system is not None:
            base_name += "-system"
        safe_name = base_name.replace(" ", "-").lower()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save World Data",
            f"{safe_name}.html",
            "HTML (*.html);;JSON (*.json)",
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lstrip(".")
        if ext == "json":
            content = obj.to_json()  # type: ignore[attr-defined]
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

    def _on_export_poster_clicked(self) -> None:
        system = self._current_system
        if system is None or system.mainworld is None:  # type: ignore[attr-defined]
            return

        base_name = getattr(system.mainworld, "name", None) or "world"  # type: ignore[attr-defined]
        safe_name = f"{base_name}-poster".replace(" ", "-").lower()

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export A3 Poster",
            f"{safe_name}.html",
            "HTML (*.html);;PDF (*.pdf)",
        )
        if not path:
            return

        # If the user picked the PDF filter but didn't type a .pdf extension,
        # Qt leaves the dialog's default .html suffix in place — honour the
        # chosen filter over the literal typed extension.
        ext = os.path.splitext(path)[1].lower()
        want_pdf = ext == ".pdf" or (ext != ".html" and "pdf" in selected_filter.lower())
        if want_pdf and ext != ".pdf":
            path += ".pdf"

        try:
            content = system.to_poster_html()  # type: ignore[attr-defined]
        except ValueError as exc:
            self._show_error(f"Poster export failed: {exc}")
            return

        if want_pdf:
            self._export_poster_pdf(content, path)
            return

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            self._show_error(f"Poster export failed: {exc}")
            return

        QMessageBox.information(
            self, "Poster Saved",
            "Saved. Open it in a browser and use Print → Save as PDF "
            "(A3, landscape) to print.",
        )

    def _export_poster_pdf(self, html: str, path: str) -> None:
        """Render the poster HTML off-screen and print it to a PDF at path.

        Uses QWebEngineView's Chromium engine (already a gen-ui dependency for
        card display) — no new PDF library needed. The view is kept alive in
        self._poster_pdf_exports until the async load/print finishes, since
        nothing else would otherwise hold a reference to it.
        """
        view = QWebEngineView()
        self._poster_pdf_exports.append(view)
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A3),
            QPageLayout.Orientation.Landscape,
            QMarginsF(0, 0, 0, 0),
        )

        def _on_load_finished(ok: bool) -> None:
            if not ok:
                self._poster_pdf_exports.remove(view)
                self._show_error("Poster PDF export failed: could not render the page.")
                return
            view.page().printToPdf(path, layout)

        def _on_pdf_finished(file_path: str, success: bool) -> None:
            self._poster_pdf_exports.remove(view)
            if success:
                QMessageBox.information(self, "Poster Saved", f"Saved to {file_path}")
            else:
                self._show_error(f"Poster PDF export failed for {file_path}")

        view.loadFinished.connect(_on_load_finished)
        view.page().pdfPrintingFinished.connect(_on_pdf_finished)
        view.setHtml(html)

    # ------------------------------------------------------------------
    # HTML file management
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Status panel
    # ------------------------------------------------------------------

    def _clear_status(self) -> None:
        self._map_btn = None
        self._survey_btn = None
        self._survey_combo = None
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _show_placeholder(self) -> None:  # pylint: disable=too-many-statements
        self._clear_status()
        self._act_save.setEnabled(False)
        self._act_export_poster.setEnabled(False)

        card = QFrame()
        card.setObjectName("onboard-card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Traveller World Generator")
        title.setObjectName("world-name")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        desc = QLabel(
            "Generates star systems and worlds"
            " using the World Builder's Handbook rules."
        )
        desc.setObjectName("dim-label")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc)

        card_layout.addSpacing(4)

        steps = QLabel("① Enter a name  →  ② Choose options  →  ③ Click Generate")
        steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(steps)

        hint = QLabel("Press Return in any field to generate.")
        hint.setObjectName("hint-label")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(hint)

        card_layout.addSpacing(4)

        tm_note = QLabel(
            "In TravellerMap mode, look up real worlds"
            " from the official Traveller universe."
        )
        tm_note.setObjectName("dim-label")
        tm_note.setWordWrap(True)
        tm_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(tm_note)

        self._status_layout.addStretch()
        self._status_layout.addWidget(card)
        self._status_layout.addStretch()

    def _show_error(self, message: str) -> None:
        self._clear_status()
        lbl = QLabel(message)
        lbl.setObjectName("error-label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_layout.addStretch()
        self._status_layout.addWidget(lbl)
        self._status_layout.addStretch()

    def _show_loading(self, message: str) -> None:
        self._clear_status()
        lbl = QLabel(message)
        lbl.setObjectName("dim-label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_layout.addStretch()
        self._status_layout.addWidget(lbl)
        self._status_layout.addStretch()

    def _start_travellermap_worker(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        sector: str,
        search_name: "str | None",
        hex_pos: "str | None",
        seed: int,
        orbital_eccentricity: bool = True,
        orbital_inclination: bool = True,
    ) -> None:
        display = search_name or hex_pos or "world"
        self._show_loading(f"Looking up {display} in {sector}…")
        if self._generate_btn is not None:
            self._generate_btn.setEnabled(False)
        worker = _TravMapWorker(sector, search_name, hex_pos, seed,
                                orbital_eccentricity=orbital_eccentricity,
                                orbital_inclination=orbital_inclination)
        worker.result.connect(self._on_worker_result)
        worker.failed.connect(self._on_worker_error)
        worker.ambiguous.connect(self._on_worker_ambiguous)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_worker_result(self, system: object) -> None:
        if self._generate_btn is not None:
            self._generate_btn.setEnabled(True)
        if self._pending_full_system:
            rng = (
                random.Random(self._pending_seed)
                if self._pending_rng is None and self._pending_seed is not None
                else self._pending_rng
            )
            self._finish_system_generation(
                system, self._pending_attach_detail, rng=rng,
            )
        else:
            world = system.mainworld  # type: ignore[attr-defined]
            if world is None:
                self._show_error("TravellerMap lookup returned no mainworld.")
                return
            self._finish_generation(world)

    def _on_worker_error(self, message: str) -> None:
        if self._generate_btn is not None:
            self._generate_btn.setEnabled(True)
        self._show_error(message)

    def _on_worker_ambiguous(self, exc: object) -> None:
        if self._generate_btn is not None:
            self._generate_btn.setEnabled(True)
        self._show_disambiguation_dialog(exc, self._pending_seed)  # type: ignore[arg-type]

    def _show_summary(self, world: object) -> None:
        self._clear_status()
        self._status_layout.addWidget(self._build_summary_header(world))
        self._status_layout.addWidget(_make_hsep(margin_v=6))
        view = QWebEngineView()
        view.setHtml(self._themed_html(world.to_html()))  # type: ignore[attr-defined]
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
        system_view.setHtml(self._themed_html(
            system.to_html(detail_attached=self._detail_attached)  # type: ignore[attr-defined]
        ))
        system_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        tabs.addTab(system_view, "System")

        # Tab 2 — Mainworld: world card HTML view
        if mw is not None:
            mw_view = QWebEngineView()
            mw_view.setHtml(self._themed_html(mw.to_html()))  # type: ignore[attr-defined]
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

        survey_btn = QPushButton("Survey Form")
        survey_btn.clicked.connect(self._on_survey_clicked)
        self._survey_btn = survey_btn
        layout.addWidget(survey_btn)

        survey_combo = QComboBox()
        survey_combo.addItem("Class 0/I Survey")
        survey_combo.addItem("Class II/III Survey")
        survey_combo.addItem("Class IV Survey")
        self._survey_combo = survey_combo
        layout.addWidget(survey_combo)

        map_btn = QPushButton("System Map")
        map_btn.clicked.connect(self._on_map_clicked)
        map_btn.setEnabled(self._opt_full_system)
        self._map_btn = map_btn
        layout.addWidget(map_btn)

        return header

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

        return header



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the Traveller World Generator desktop application."""
    # Suppress the harmless TASK_CATEGORY_POLICY stderr noise from the
    # Chromium renderer subprocess (QtWebEngine on macOS, KERN_INVALID_ARGUMENT).
    # Must be set before QApplication is constructed.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--log-level=3")
    app = QApplication(sys.argv)
    app.setApplicationName("Traveller World Generator")
    window = AppWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
