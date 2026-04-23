"""
Traveller System Generator — GTK4 UI

Mongoose Publishing Traveller is copyright Mongoose Publishing.
Used under the Mongoose Publishing Fair Use Policy for non-commercial purposes.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio  # noqa: E402  (must follow gi.require_version)


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Traveller System Generator")
        self.set_default_size(900, 600)


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
