"""
gen-ui/app.py
=============
Traveller World Generator — GTK4 desktop UI.

Generates mainworlds using the CRB rules in traveller_world_gen.py and
displays the result as an HTML card in the system default browser.
WebKitGTK is not available on macOS via Homebrew, so the HTML output is
written to a temp file and opened with Gio.AppInfo.launch_default_for_uri.

World data can also be saved to a user-chosen file in JSON, plain text,
or HTML format via Gtk.FileDialog.

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

import gi  # noqa: E402

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

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
# CSS
# ---------------------------------------------------------------------------

_CSS = b"""
.zone-green   { background-color: #27ae60; color: white;
                padding: 2px 10px; border-radius: 4px; }
.zone-amber   { background-color: #e67e22; color: white;
                padding: 2px 10px; border-radius: 4px; }
.zone-red     { background-color: #c0392b; color: white;
                padding: 2px 10px; border-radius: 4px; }
.uwp-label    { font-family: monospace; font-size: 18pt; font-weight: bold; }
.world-name   { font-size: 16pt; font-weight: bold; }
.trade-codes  { font-family: monospace; font-size: 11pt; }
.error-label  { color: #c0392b; font-weight: bold; }
.hint-label   { font-style: italic; }
.stat-value   { font-size: 13pt; font-weight: bold; }
.stat-sub     { font-size: 9pt; }
.section-label{ font-size: 9pt; font-weight: bold; }
.row-label    { font-size: 10pt; }
.row-value    { font-size: 10pt; font-weight: bold; }
label.danger-value { font-size: 10pt; font-weight: bold; color: #c0392b; }
label.tc-badge     { background-color: #faece7; color: #712b13;
                     padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
.table-header { font-size: 9pt; font-weight: bold; }
.table-cell   { font-size: 10pt; }
.table-mw     { font-size: 10pt; font-weight: bold; }
.table-dim    { font-size: 10pt; }
.table-moon   { font-size: 9pt; color: #888888; }
"""

_ZONE_CLASS = {"Green": "zone-green", "Amber": "zone-amber", "Red": "zone-red"}

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


def _orbit_profile(orbit: object) -> str:
    """Short profile string for an orbit slot in the detail table."""
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


def _detail_row(label_text: str, value_text: str, danger: bool = False) -> Gtk.Box:
    """One label/value row for the Physical and Society detail cards."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_margin_top(2)
    row.set_margin_bottom(2)
    lbl = Gtk.Label(label=label_text)
    lbl.add_css_class("row-label")
    lbl.set_halign(Gtk.Align.START)
    lbl.set_hexpand(True)
    val = Gtk.Label(label=value_text)
    val.add_css_class("danger-value" if danger else "row-value")
    val.set_halign(Gtk.Align.END)
    val.set_xalign(1.0)
    val.set_justify(Gtk.Justification.RIGHT)
    val.set_wrap(True)
    val.set_max_width_chars(22)
    row.append(lbl)
    row.append(val)
    return row

# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Traveller World Generator")
        self.set_default_size(800, 620)
        self._html_path: str | None = None
        self._current_world: object | None = None
        self._current_system: object | None = None
        self._detail_attached: bool = False
        self._seed_auto: bool = False   # True when seed field was auto-filled
        self._apply_css()
        self._build_ui()

    def _apply_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.set_child(root)

        root.append(self._build_controls())

        opt_sep = Gtk.Separator()
        opt_sep.set_margin_top(8)
        opt_sep.set_margin_bottom(8)
        root.append(opt_sep)

        root.append(self._build_source_row())
        root.append(self._build_options_row())

        sep = Gtk.Separator()
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        root.append(sep)

        self._status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._status_box.set_vexpand(True)
        root.append(self._status_box)

        self._show_placeholder()

    def _build_controls(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        row.append(Gtk.Label(label="Name:"))

        self._name_entry = Gtk.Entry()
        self._name_entry.set_placeholder_text("World name (optional)")
        self._name_entry.set_hexpand(True)
        self._name_entry.connect("activate", self._on_generate)
        row.append(self._name_entry)

        row.append(Gtk.Label(label="Seed:"))

        self._seed_entry = Gtk.Entry()
        self._seed_entry.set_placeholder_text("Integer (optional)")
        self._seed_entry.set_width_chars(14)
        self._seed_entry.connect("activate", self._on_generate)
        self._seed_entry.connect("changed", self._on_seed_changed)
        row.append(self._seed_entry)

        clear_btn = Gtk.Button(label="New Seed")
        clear_btn.connect("clicked", self._on_clear_seed)
        row.append(clear_btn)

        btn = Gtk.Button(label="Generate")
        btn.add_css_class("suggested-action")
        btn.connect("clicked", self._on_generate)
        row.append(btn)

        return row

    def _build_source_row(self) -> Gtk.Box:
        """Source selection: Procedural vs TravellerMap with sector/name/hex fields."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Radio group — Procedural / TravellerMap
        self._radio_procedural = Gtk.CheckButton(label="Procedural")
        self._radio_procedural.set_active(True)
        self._radio_procedural.connect("notify::active", self._on_source_toggled)
        row.append(self._radio_procedural)

        self._radio_travellermap = Gtk.CheckButton(label="TravellerMap")
        self._radio_travellermap.set_group(self._radio_procedural)
        row.append(self._radio_travellermap)

        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(4)
        vsep.set_margin_end(4)
        row.append(vsep)

        sector_lbl = Gtk.Label(label="Sector:")
        sector_lbl.set_valign(Gtk.Align.CENTER)
        row.append(sector_lbl)
        self._sector_entry = Gtk.Entry()
        self._sector_entry.set_placeholder_text("e.g. Spinward Marches")
        self._sector_entry.set_width_chars(20)
        self._sector_entry.set_valign(Gtk.Align.CENTER)
        row.append(self._sector_entry)

        # Grid keeps Name/Hex label column the same width so entries left-align.
        name_hex_grid = Gtk.Grid()
        name_hex_grid.set_row_spacing(4)
        name_hex_grid.set_column_spacing(6)

        name_lbl = Gtk.Label(label="Name:")
        name_lbl.set_halign(Gtk.Align.END)
        self._tm_name_entry = Gtk.Entry()
        self._tm_name_entry.set_placeholder_text("e.g. Regina")
        self._tm_name_entry.set_width_chars(14)
        self._tm_name_entry.connect("activate", self._on_generate)
        name_hex_grid.attach(name_lbl, 0, 0, 1, 1)
        name_hex_grid.attach(self._tm_name_entry, 1, 0, 1, 1)

        hex_lbl = Gtk.Label(label="Hex:")
        hex_lbl.set_halign(Gtk.Align.END)
        self._hex_entry = Gtk.Entry()
        self._hex_entry.set_placeholder_text("e.g. 1910")
        self._hex_entry.set_width_chars(6)
        self._hex_entry.connect("activate", self._on_generate)
        optional_lbl = Gtk.Label(label="Optional")
        optional_lbl.add_css_class("hint-label")
        optional_lbl.add_css_class("dim-label")
        name_hex_grid.attach(hex_lbl, 0, 1, 1, 1)
        name_hex_grid.attach(self._hex_entry, 1, 1, 1, 1)
        name_hex_grid.attach(optional_lbl, 2, 1, 1, 1)

        row.append(name_hex_grid)

        self._sector_entry.set_sensitive(False)
        self._tm_name_entry.set_sensitive(False)
        self._hex_entry.set_sensitive(False)

        return row

    def _build_options_row(self) -> Gtk.Box:
        """Generation options: mode, detail, and output format."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Generation mode checkboxes
        self._check_full_system = Gtk.CheckButton(label="Full system")
        self._check_full_system.connect("notify::active", self._on_full_system_toggled)
        row.append(self._check_full_system)

        self._check_attach_detail = Gtk.CheckButton(label="Attach detail")
        self._check_attach_detail.set_sensitive(False)
        row.append(self._check_attach_detail)

        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(4)
        vsep.set_margin_end(4)
        row.append(vsep)

        row.append(Gtk.Label(label="Format:"))
        self._gen_format_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(["HTML", "JSON", "Text"])
        )
        self._gen_format_dropdown.set_selected(0)
        row.append(self._gen_format_dropdown)

        return row

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_clear_seed(self, _widget: object) -> None:
        self._seed_auto = False
        self._seed_entry.set_text(str(secrets.randbelow(2 ** 31)))

    def _on_seed_changed(self, _widget: object) -> None:
        if not self._seed_auto:
            return
        # User edited the field — treat whatever is now typed as intentional.
        self._seed_auto = False

    def _on_full_system_toggled(self, _widget: object, _param: object) -> None:
        active = self._check_full_system.get_active()
        self._check_attach_detail.set_sensitive(active)
        if not active:
            self._check_attach_detail.set_active(False)

    def _on_source_toggled(self, _widget: object, _param: object) -> None:
        procedural = self._radio_procedural.get_active()
        self._sector_entry.set_sensitive(not procedural)
        self._tm_name_entry.set_sensitive(not procedural)
        self._hex_entry.set_sensitive(not procedural)

    def _on_generate(self, _widget: object) -> None:
        name = self._name_entry.get_text().strip() or "Unknown"
        seed_raw = self._seed_entry.get_text().strip()

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
        self._seed_entry.set_text(str(seed))

        full_system = self._check_full_system.get_active()
        attach_detail_flag = full_system and self._check_attach_detail.get_active()

        if self._radio_travellermap.get_active():
            sector = self._sector_entry.get_text().strip()
            search_name = self._tm_name_entry.get_text().strip() or None
            hex_pos = self._hex_entry.get_text().strip() or None
            if not sector:
                self._show_error("Sector is required for TravellerMap lookup.")
                return
            if not search_name and not hex_pos:
                self._show_error("Enter a world name or hex for TravellerMap lookup.")
                return
            self._do_travellermap_generation(sector, search_name, hex_pos, seed, full_system, attach_detail_flag)
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

    def _finish_system_generation(self, system: object, attach_detail_flag: bool = False) -> None:
        self._current_system = system
        self._current_world = system.mainworld  # type: ignore[attr-defined]
        if attach_detail_flag:
            _attach_detail(system)  # type: ignore[arg-type]
        self._detail_attached = attach_detail_flag
        path = self._write_html(system.to_html(detail_attached=attach_detail_flag))  # type: ignore[attr-defined]
        if path is not None:
            self._html_path = path
        self._show_system_summary(system)

    def _show_disambiguation_dialog(
        self, error: AmbiguousWorldError, seed: int,
        full_system: bool = False, attach_detail_flag: bool = False,
    ) -> None:
        dialog = Gtk.Window()
        dialog.set_title("Ambiguous World Name")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        lbl = Gtk.Label(
            label=f"Multiple worlds named '{error.name}' found in {error.sector}."
                  f"\nSelect one:"
        )
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        first_radio: "Gtk.CheckButton | None" = None
        radios: "list[tuple[Gtk.CheckButton, str]]" = []
        for world_name, hex_code in error.candidates:
            radio = Gtk.CheckButton(label=f"{world_name}  —  hex {hex_code}")
            if first_radio is None:
                first_radio = radio
                radio.set_active(True)
            else:
                radio.set_group(first_radio)
            radios.append((radio, hex_code))
            box.append(radio)

        sep = Gtk.Separator()
        sep.set_margin_top(4)
        box.append(sep)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: dialog.close())
        btn_row.append(cancel_btn)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.add_css_class("suggested-action")

        def _on_ok(_btn: object) -> None:
            selected = next(
                (h for radio, h in radios if radio.get_active()), None
            )
            dialog.close()
            if selected:
                self._do_travellermap_generation(
                    error.sector, None, selected, seed, full_system, attach_detail_flag
                )

        ok_btn.connect("clicked", _on_ok)
        btn_row.append(ok_btn)
        box.append(btn_row)

        dialog.set_child(box)
        dialog.present()

    def _on_save_clicked(self, _btn: object) -> None:
        obj = self._current_system or self._current_world
        if obj is None:
            return

        idx = self._format_dropdown.get_selected()
        label, ext = _FORMATS[idx]

        base_name = getattr(self._current_world, "name", None) or "world"
        if self._current_system is not None:
            base_name = base_name + "-system"
        safe_name = base_name.replace(" ", "-").lower()

        filters = Gio.ListStore.new(Gtk.FileFilter)
        ff = Gtk.FileFilter()
        ff.set_name(f"{label} files (*.{ext})")
        ff.add_pattern(f"*.{ext}")
        filters.append(ff)

        dialog = Gtk.FileDialog()
        dialog.set_title(f"Save World Data as {label}")
        dialog.set_initial_name(f"{safe_name}.{ext}")
        dialog.set_filters(filters)
        dialog.set_default_filter(ff)
        dialog.save(self, None, self._on_save_finish)

    def _on_save_finish(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.save_finish(result)
        except Exception:  # pylint: disable=broad-exception-caught
            return  # user cancelled or dialog error

        if gfile is None:
            return
        path = gfile.get_path()
        obj = self._current_system or self._current_world
        if path is None or obj is None:
            return

        idx = self._format_dropdown.get_selected()
        _, ext = _FORMATS[idx]

        if ext == "json":
            content = obj.to_json()                             # type: ignore[attr-defined]
        elif ext == "txt":
            content = obj.summary()                             # type: ignore[attr-defined]
        else:
            if self._current_system is not None:
                content = obj.to_html(detail_attached=self._detail_attached)  # type: ignore[attr-defined]
            else:
                content = obj.to_html()                         # type: ignore[attr-defined]

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
        uri = Gio.File.new_for_path(path).get_uri()
        Gio.AppInfo.launch_default_for_uri(uri, None)

    # ------------------------------------------------------------------
    # Status panel
    # ------------------------------------------------------------------

    def _clear_status(self) -> None:
        while child := self._status_box.get_first_child():
            self._status_box.remove(child)

    def _show_placeholder(self) -> None:
        self._clear_status()
        lbl = Gtk.Label(label="Enter a name and click Generate.")
        lbl.add_css_class("dim-label")
        lbl.set_vexpand(True)
        lbl.set_valign(Gtk.Align.CENTER)
        self._status_box.append(lbl)

    def _show_error(self, message: str) -> None:
        self._clear_status()
        lbl = Gtk.Label(label=message)
        lbl.add_css_class("error-label")
        lbl.set_valign(Gtk.Align.CENTER)
        lbl.set_vexpand(True)
        self._status_box.append(lbl)

    def _show_system_summary(self, system: object) -> None:
        self._clear_status()
        mw = system.mainworld  # type: ignore[attr-defined]

        header, orbit_switch = self._build_system_summary_header(system)
        self._status_box.append(header)

        sep = Gtk.Separator()
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        self._status_box.append(sep)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        card.set_margin_start(2)
        card.set_margin_end(2)

        stellar_card = self._build_stellar_card(system)
        orbits_card = self._build_orbits_card(system, detail_attached=self._detail_attached)
        card.append(stellar_card)
        card.append(orbits_card)

        if mw is not None:
            mw_frame = Gtk.Frame(label="Mainworld")
            mw_frame.set_child(self._build_world_card(mw))
            card.append(mw_frame)

        def _on_orbit_switch(switch: Gtk.Switch, _param: object) -> None:
            visible = switch.get_active()
            stellar_card.set_visible(visible)
            orbits_card.set_visible(visible)

        orbit_switch.connect("notify::active", _on_orbit_switch)

        scroll.set_child(card)
        self._status_box.append(scroll)

    def _build_system_summary_header(
        self, system: object
    ) -> "tuple[Gtk.Box, Gtk.Switch]":
        """Header bar for full-system view: world info, Stellar & Orbits switch, actions."""
        mw = system.mainworld  # type: ignore[attr-defined]
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        if mw is not None:
            name_lbl = Gtk.Label(label=mw.name)
            name_lbl.add_css_class("world-name")
            bar.append(name_lbl)

            uwp_lbl = Gtk.Label(label=mw.uwp())
            uwp_lbl.add_css_class("uwp-label")
            bar.append(uwp_lbl)

            zone_lbl = Gtk.Label(label=f"  {mw.travel_zone}  ")
            zone_lbl.add_css_class(_ZONE_CLASS.get(mw.travel_zone, "zone-green"))
            zone_lbl.set_valign(Gtk.Align.CENTER)
            bar.append(zone_lbl)
        else:
            stars = system.stellar_system.stars  # type: ignore[attr-defined]
            lbl = Gtk.Label(label=f"System — {len(stars)} star(s)")
            lbl.add_css_class("world-name")
            bar.append(lbl)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)

        switch_lbl = Gtk.Label(label="Stellar && Orbits")
        switch_lbl.add_css_class("hint-label")
        bar.append(switch_lbl)

        orbit_switch = Gtk.Switch()
        orbit_switch.set_active(True)
        orbit_switch.set_valign(Gtk.Align.CENTER)
        bar.append(orbit_switch)

        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(6)
        vsep.set_margin_end(6)
        bar.append(vsep)

        bar.append(self._build_action_buttons())
        return bar, orbit_switch

    def _build_action_buttons(self) -> Gtk.Box:
        """Open in Browser + Save as dropdown + Save button."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        open_btn = Gtk.Button(label="Open in Browser")
        open_btn.connect(
            "clicked",
            lambda _: self._open_in_browser(self._html_path)  # type: ignore[arg-type]
            if self._html_path else None,
        )
        box.append(open_btn)
        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(4)
        vsep.set_margin_end(4)
        box.append(vsep)
        box.append(Gtk.Label(label="Save as:"))
        self._format_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new([lbl for lbl, _ in _FORMATS])
        )
        self._format_dropdown.set_selected(0)
        box.append(self._format_dropdown)
        save_btn = Gtk.Button(label="Save…")
        save_btn.connect("clicked", self._on_save_clicked)
        box.append(save_btn)
        return box

    def _build_stellar_card(self, system: object) -> Gtk.Frame:
        """Stars table: Designation | Classification | Mass | Temp | Luminosity | Orbit AU."""
        frame = Gtk.Frame(label="Stellar System")
        grid = Gtk.Grid()
        grid.set_row_spacing(4)
        grid.set_column_spacing(16)
        grid.set_margin_top(6)
        grid.set_margin_bottom(8)
        grid.set_margin_start(10)
        grid.set_margin_end(10)

        headers = ["Desig", "Type", "Mass (M☉)", "Temp (K)", "Lum (L☉)", "Orbit (AU)"]
        for col, hdr in enumerate(headers):
            lbl = Gtk.Label(label=hdr)
            lbl.add_css_class("table-header")
            lbl.set_halign(Gtk.Align.START if col < 2 else Gtk.Align.END)
            grid.attach(lbl, col, 0, 1, 1)

        stars = system.stellar_system.stars  # type: ignore[attr-defined]
        for row, star in enumerate(stars, start=1):
            orbit_str = f"{star.orbit_au:.3f}" if star.orbit_au else "—"
            cells = [
                (star.designation,                   Gtk.Align.START),
                (star.classification(),              Gtk.Align.START),
                (f"{star.mass:.3f}",                 Gtk.Align.END),
                (f"{star.temperature:,}",            Gtk.Align.END),
                (f"{star.luminosity:.4f}",           Gtk.Align.END),
                (orbit_str,                          Gtk.Align.END),
            ]
            for col, (text, align) in enumerate(cells):
                lbl = Gtk.Label(label=text)
                lbl.add_css_class("table-cell")
                lbl.set_halign(align)
                grid.attach(lbl, col, row, 1, 1)

        frame.set_child(grid)
        return frame

    def _build_orbits_card(self, system: object, detail_attached: bool = False) -> Gtk.Frame:
        """Orbits table; with detail: includes moon sub-rows per orbit."""
        frame = Gtk.Frame(label="System Orbits")
        grid = Gtk.Grid()
        grid.set_row_spacing(3)
        grid.set_column_spacing(14)
        grid.set_margin_top(6)
        grid.set_margin_bottom(8)
        grid.set_margin_start(10)
        grid.set_margin_end(10)

        if detail_attached:
            headers = ["Star", "Orbit#", "AU", "Type", "Profile", "Codes", "HZ", "Zone"]
            start_cols = {0, 3, 4, 5, 6, 7}
        else:
            headers = ["Star", "Orbit#", "AU", "Type", "HZ", "Zone"]
            start_cols = {0, 3, 4, 5}

        for col, hdr in enumerate(headers):
            lbl = Gtk.Label(label=hdr)
            lbl.add_css_class("table-header")
            lbl.set_halign(Gtk.Align.START if col in start_cols else Gtk.Align.END)
            grid.attach(lbl, col, 0, 1, 1)

        orbits = system.system_orbits.orbits             # type: ignore[attr-defined]
        mw_orbit = system.system_orbits.mainworld_orbit  # type: ignore[attr-defined]

        grid_row = 1
        for orbit in orbits:
            is_mw = (orbit is mw_orbit)
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
                    codes_str = " ".join(detail.trade_codes)           # type: ignore[attr-defined]
                cells: list[tuple[str, Gtk.Align]] = [
                    (orbit.star_designation,         Gtk.Align.START),
                    (f"{orbit.orbit_number:.2f}",    Gtk.Align.END),
                    (f"{orbit.orbit_au:.3f}",        Gtk.Align.END),
                    (type_str,                       Gtk.Align.START),
                    (profile_str,                    Gtk.Align.START),
                    (codes_str,                      Gtk.Align.START),
                    (hz_str,                         Gtk.Align.START),
                    (zone_str,                       Gtk.Align.START),
                ]
            else:
                detail = None
                cells = [
                    (orbit.star_designation,         Gtk.Align.START),
                    (f"{orbit.orbit_number:.2f}",    Gtk.Align.END),
                    (f"{orbit.orbit_au:.3f}",        Gtk.Align.END),
                    (type_str,                       Gtk.Align.START),
                    (hz_str,                         Gtk.Align.START),
                    (zone_str,                       Gtk.Align.START),
                ]

            for col, (text, align) in enumerate(cells):
                lbl = Gtk.Label(label=text)
                lbl.add_css_class(css)
                lbl.set_halign(align)
                grid.attach(lbl, col, grid_row, 1, 1)
            grid_row += 1

            # Moon sub-rows when detail is attached
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
                        ("",                   Gtk.Align.START),
                        (f"↳ m{mi}",           Gtk.Align.END),
                        ("",                   Gtk.Align.START),
                        (moon_type,            Gtk.Align.START),
                        (moon_profile,         Gtk.Align.START),
                        (moon_codes,           Gtk.Align.START),
                        ("",                   Gtk.Align.START),
                        ("",                   Gtk.Align.START),
                    ]
                    for col, (text, align) in enumerate(moon_cells):
                        lbl = Gtk.Label(label=text)
                        lbl.add_css_class("table-moon")
                        lbl.set_halign(align)
                        grid.attach(lbl, col, grid_row, 1, 1)
                    grid_row += 1

        frame.set_child(grid)
        return frame

    def _show_summary(self, world: object) -> None:
        self._clear_status()
        self._status_box.append(self._build_summary_header(world))
        sep = Gtk.Separator()
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        self._status_box.append(sep)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self._build_world_card(world))
        self._status_box.append(scroll)

    def _build_summary_header(self, world: object) -> Gtk.Box:
        """Fixed header bar: name, UWP, zone badge, spacer, actions."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        name_lbl = Gtk.Label(label=world.name)  # type: ignore[attr-defined]
        name_lbl.add_css_class("world-name")
        bar.append(name_lbl)

        uwp_lbl = Gtk.Label(label=world.uwp())  # type: ignore[attr-defined]
        uwp_lbl.add_css_class("uwp-label")
        bar.append(uwp_lbl)

        zone_lbl = Gtk.Label(label=f"  {world.travel_zone}  ")  # type: ignore[attr-defined]
        zone_lbl.add_css_class(_ZONE_CLASS.get(world.travel_zone, "zone-green"))  # type: ignore[attr-defined]
        zone_lbl.set_valign(Gtk.Align.CENTER)
        bar.append(zone_lbl)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)

        bar.append(self._build_action_buttons())
        return bar

    def _build_world_card(self, world: object) -> Gtk.Box:
        """Scrollable card: stat boxes + Physical/Society cards + trade codes + notes."""
        w = world
        d = w.to_dict()  # type: ignore[attr-defined]

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        card.set_margin_start(2)
        card.set_margin_end(2)

        card.append(self._build_stat_row(w, d))
        card.append(self._build_detail_cards(w, d))
        card.append(self._build_trade_codes(w))
        notes = self._build_notes(w)
        if notes:
            card.append(notes)
        return card

    def _build_stat_row(self, w: object, d: dict) -> Gtk.Box:
        """Three equal-width stat boxes: Starport | Size | Tech Level."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_homogeneous(True)

        def stat_frame(title: str, value: str, subtitle: str) -> Gtk.Frame:
            frame = Gtk.Frame(label=title)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_top(4)
            box.set_margin_bottom(6)
            box.set_margin_start(8)
            box.set_margin_end(8)
            v = Gtk.Label(label=value)
            v.add_css_class("stat-value")
            v.set_halign(Gtk.Align.START)
            v.set_wrap(True)
            s = Gtk.Label(label=subtitle)
            s.add_css_class("stat-sub")
            s.add_css_class("dim-label")
            s.set_halign(Gtk.Align.START)
            s.set_wrap(True)
            box.append(v)
            box.append(s)
            frame.set_child(box)
            return frame

        sp = w.starport  # type: ignore[attr-defined]
        row.append(stat_frame(
            "Starport",
            f"{sp} — {STARPORT_QUALITY_LABEL.get(sp, '?')}",
            STARPORT_FACILITY_DETAIL.get(sp, ""),
        ))
        row.append(stat_frame(
            "Size",
            f"{_to_hex(w.size)} — {d['size']['diameter_km']} km",  # type: ignore[attr-defined]
            f"Gravity: {d['size']['surface_gravity']}",
        ))
        row.append(stat_frame(
            "Tech Level",
            _to_hex(w.tech_level),  # type: ignore[attr-defined]
            _tl_era(w.tech_level),  # type: ignore[attr-defined]
        ))
        return row

    def _build_detail_cards(self, w: object, d: dict) -> Gtk.Box:
        """Side-by-side Physical and Society detail cards."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Physical
        phys = Gtk.Frame(label="Physical")
        phys.set_hexpand(True)
        pb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        pb.set_margin_top(4)
        pb.set_margin_bottom(6)
        pb.set_margin_start(8)
        pb.set_margin_end(8)
        gear = d["atmosphere"]["survival_gear"]
        gear_danger = gear not in ("None", "Varies")
        for lbl, val, danger in [
            ("Atmosphere",      f"{_to_hex(w.atmosphere)} — {d['atmosphere']['name']}", False),  # type: ignore[attr-defined]
            ("Survival gear",   gear,                                                    gear_danger),
            ("Temperature",     w.temperature,                                           False),   # type: ignore[attr-defined]
            ("Hydrographics",   f"{_to_hex(w.hydrographics)} — {d['hydrographics']['description'].split(' (')[0]}", False),  # type: ignore[attr-defined]
            ("Gas giants",      str(w.gas_giant_count) if w.has_gas_giant else "None",  False),   # type: ignore[attr-defined]
            ("Planetoid belts", str(w.belt_count),                                      False),   # type: ignore[attr-defined]
            ("PBG",             f"{w.population_multiplier}{w.belt_count}{w.gas_giant_count}", False),  # type: ignore[attr-defined]
        ]:
            pb.append(_detail_row(lbl, val, danger))
        phys.set_child(pb)
        row.append(phys)

        # Society
        soc = Gtk.Frame(label="Society")
        soc.set_hexpand(True)
        sb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sb.set_margin_top(4)
        sb.set_margin_bottom(6)
        sb.set_margin_start(8)
        sb.set_margin_end(8)
        pop_str = f"{_to_hex(w.population)} — {d['population']['range']}"  # type: ignore[attr-defined]
        if w.population > 0:  # type: ignore[attr-defined]
            pop_str += f"  (P={w.population_multiplier})"  # type: ignore[attr-defined]
        bases_str = "  ".join(_BASE_FULL.get(b, b) for b in w.bases) or "None"  # type: ignore[attr-defined]
        for lbl, val in [
            ("Population", pop_str),
            ("Government", f"{_to_hex(w.government)} — {d['government']['name']}"),  # type: ignore[attr-defined]
            ("Law level",  _to_hex(w.law_level)),  # type: ignore[attr-defined]
            ("Bases",      bases_str),
        ]:
            sb.append(_detail_row(lbl, val))
        soc.set_child(sb)
        row.append(soc)

        return row

    def _build_trade_codes(self, w: object) -> Gtk.Box:
        """Trade code badges in a flow layout."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        hdr = Gtk.Label(label="Trade codes")
        hdr.add_css_class("section-label")
        hdr.set_halign(Gtk.Align.START)
        box.append(hdr)

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(12)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)

        if w.trade_codes:  # type: ignore[attr-defined]
            for tc in w.trade_codes:  # type: ignore[attr-defined]
                badge = Gtk.Label(label=f"{tc} — {_TRADE_CODE_FULL.get(tc, tc)}")
                badge.add_css_class("tc-badge")
                badge.set_margin_top(2)
                badge.set_margin_bottom(2)
                flow.append(badge)
        else:
            none_lbl = Gtk.Label(label="None")
            none_lbl.add_css_class("dim-label")
            flow.append(none_lbl)

        box.append(flow)
        return box

    def _build_notes(self, w: object) -> "Gtk.Frame | None":
        """Notes frame, or None if there are no notes."""
        if not w.notes:  # type: ignore[attr-defined]
            return None
        frame = Gtk.Frame(label="Notes")
        nb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        nb.set_margin_top(4)
        nb.set_margin_bottom(6)
        nb.set_margin_start(8)
        nb.set_margin_end(8)
        for note in w.notes:  # type: ignore[attr-defined]
            lbl = Gtk.Label(label=f"• {note}")
            lbl.add_css_class("stat-sub")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_wrap(True)
            nb.append(lbl)
        frame.set_child(nb)
        return frame


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class App(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="com.example.traveller-world-gen",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        # Connect to the startup signal rather than overriding do_startup.
        # Overriding do_startup in PyGObject does not satisfy GLib's C-level
        # chain-up check even when super() is called, causing a segfault.
        self.connect("startup", self._on_startup)

    def _on_startup(self, _app: object) -> None:
        # On macOS with GTK4's Quartz backend, <primary> maps to Control, not
        # Command. The Command key is <meta>. Both are registered so Ctrl and
        # Cmd variants work. Alt+F4 on Windows is handled by the window manager.
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q", "<meta>q"])
        self.set_accels_for_action("window.close", ["<primary>w", "<meta>w"])

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = AppWindow(self)
        win.present()


def main() -> None:
    app = App()
    app.run(None)


if __name__ == "__main__":
    main()
