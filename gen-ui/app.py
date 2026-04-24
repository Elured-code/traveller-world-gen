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

from traveller_world_gen import generate_world  # noqa: E402

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = b"""
.zone-green  { background-color: #27ae60; color: white;
               padding: 2px 10px; border-radius: 4px; }
.zone-amber  { background-color: #e67e22; color: white;
               padding: 2px 10px; border-radius: 4px; }
.zone-red    { background-color: #c0392b; color: white;
               padding: 2px 10px; border-radius: 4px; }
.uwp-label   { font-family: monospace; font-size: 18pt; font-weight: bold; }
.world-name  { font-size: 16pt; font-weight: bold; }
.trade-codes { font-family: monospace; font-size: 11pt; }
.error-label { color: #c0392b; font-weight: bold; }
.hint-label  { font-style: italic; }
"""

_ZONE_CLASS = {"Green": "zone-green", "Amber": "zone-amber", "Red": "zone-red"}

# Save format definitions: (label, file extension)
_FORMATS = [
    ("JSON",  "json"),
    ("Text",  "txt"),
    ("HTML",  "html"),
]

# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Traveller World Generator")
        self.set_default_size(720, 420)
        self._html_path: str | None = None
        self._current_world: object | None = None
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
        """Source selection: Procedural vs TravellerMap with sector/hex fields."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Radio group — Procedural / TravellerMap
        self._radio_procedural = Gtk.CheckButton(label="Procedural")
        self._radio_procedural.set_active(True)
        row.append(self._radio_procedural)

        self._radio_travellermap = Gtk.CheckButton(label="TravellerMap")
        self._radio_travellermap.set_group(self._radio_procedural)
        row.append(self._radio_travellermap)

        vsep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vsep.set_margin_start(4)
        vsep.set_margin_end(4)
        row.append(vsep)

        row.append(Gtk.Label(label="Sector:"))
        self._sector_entry = Gtk.Entry()
        self._sector_entry.set_placeholder_text("e.g. Spinward Marches")
        self._sector_entry.set_width_chars(20)
        row.append(self._sector_entry)

        row.append(Gtk.Label(label="Hex:"))
        self._hex_entry = Gtk.Entry()
        self._hex_entry.set_placeholder_text("e.g. 1910")
        self._hex_entry.set_width_chars(6)
        row.append(self._hex_entry)

        return row

    def _build_options_row(self) -> Gtk.Box:
        """Generation options: mode, detail, and output format."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Generation mode checkboxes
        self._check_full_system = Gtk.CheckButton(label="Full system")
        row.append(self._check_full_system)

        self._check_attach_detail = Gtk.CheckButton(label="Attach detail")
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

        world = generate_world(name)
        self._current_world = world

        path = self._write_html(world.to_html())
        if path is None:
            self._show_error("Could not write HTML output file.")
            return
        self._html_path = path
        self._show_summary(world)
        self._open_in_browser(path)

    def _on_save_clicked(self, _btn: object) -> None:
        if self._current_world is None:
            return

        idx = self._format_dropdown.get_selected()
        label, ext = _FORMATS[idx]

        safe_name = (
            getattr(self._current_world, "name", "world")
            .replace(" ", "-")
            .lower()
        )

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
        if path is None or self._current_world is None:
            return

        idx = self._format_dropdown.get_selected()
        _, ext = _FORMATS[idx]

        if ext == "json":
            content = self._current_world.to_json()       # type: ignore[attr-defined]
        elif ext == "txt":
            content = self._current_world.summary()       # type: ignore[attr-defined]
        else:
            content = self._current_world.to_html()       # type: ignore[attr-defined]

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

    def _show_summary(self, world: object) -> None:
        self._clear_status()

        # Name + UWP + travel zone
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_halign(Gtk.Align.CENTER)
        header.set_valign(Gtk.Align.CENTER)
        header.set_vexpand(True)

        name_lbl = Gtk.Label(label=world.name)  # type: ignore[attr-defined]
        name_lbl.add_css_class("world-name")
        header.append(name_lbl)

        uwp_lbl = Gtk.Label(label=world.uwp())  # type: ignore[attr-defined]
        uwp_lbl.add_css_class("uwp-label")
        header.append(uwp_lbl)

        zone_lbl = Gtk.Label(label=f"  {world.travel_zone}  ")  # type: ignore[attr-defined]
        zone_lbl.add_css_class(_ZONE_CLASS.get(world.travel_zone, "zone-green"))  # type: ignore[attr-defined]
        zone_lbl.set_valign(Gtk.Align.CENTER)
        header.append(zone_lbl)

        self._status_box.append(header)

        # Trade codes + bases
        tc = "  ".join(world.trade_codes) if world.trade_codes else "—"  # type: ignore[attr-defined]
        bases = "  ".join(world.bases) if world.bases else "—"           # type: ignore[attr-defined]
        detail = Gtk.Label(label=f"Trade codes: {tc}     Bases: {bases}")
        detail.add_css_class("trade-codes")
        detail.set_halign(Gtk.Align.CENTER)
        self._status_box.append(detail)

        # Action row: Reopen + Save as
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_row.set_halign(Gtk.Align.CENTER)

        reopen_btn = Gtk.Button(label="Reopen HTML Card")
        reopen_btn.connect(
            "clicked",
            lambda _: self._open_in_browser(self._html_path)  # type: ignore[arg-type]
            if self._html_path else None,
        )
        action_row.append(reopen_btn)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(4)
        sep.set_margin_end(4)
        action_row.append(sep)

        action_row.append(Gtk.Label(label="Save as:"))

        self._format_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new([label for label, _ in _FORMATS])
        )
        self._format_dropdown.set_selected(0)
        action_row.append(self._format_dropdown)

        save_btn = Gtk.Button(label="Save…")
        save_btn.connect("clicked", self._on_save_clicked)
        action_row.append(save_btn)

        self._status_box.append(action_row)

        hint = Gtk.Label(label="HTML card opened in default browser")
        hint.add_css_class("hint-label")
        hint.add_css_class("dim-label")
        hint.set_halign(Gtk.Align.CENTER)
        self._status_box.append(hint)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class App(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="com.example.traveller-world-gen",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

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
