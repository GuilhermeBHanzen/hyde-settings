"""Base class for the app's pages: a vertical box holding one Adw.PreferencesPage."""
from contextlib import contextmanager

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


class Page(Gtk.Box):
    key = ""
    title = ""
    icon = ""

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.app = app
        self.prefs = Adw.PreferencesPage(vexpand=True)
        self.append(self.prefs)
        self._syncing = False

    @contextmanager
    def syncing(self):
        """Programmatic widget updates inside this block do not count as user changes."""
        self._syncing = True
        try:
            yield
        finally:
            self._syncing = False

    def changed(self):
        if not self._syncing:
            self.app.changed()

    def refresh(self):
        """Re-read app.pending and live state into the widgets."""

    def filter(self, text):
        """Apply the global search text; pages without a list ignore it."""
