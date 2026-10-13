"""GTK application: owns saved and pending settings, wires pages to the apply transaction."""
import copy
import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib  # noqa: E402

from hyde_settings import hook, store  # noqa: E402
from hyde_settings.apply import Applier  # noqa: E402
from hyde_settings.hypr import Hypr  # noqa: E402
from hyde_settings.window import MainWindow  # noqa: E402

# GLib.unix_signal_add is deprecated (PyGIDeprecationWarning); prefer GLibUnix when available.
try:
    gi.require_version("GLibUnix", "2.0")
    from gi.repository import GLibUnix

    unix_signal_add = GLibUnix.signal_add
except (ImportError, ValueError):
    unix_signal_add = GLib.unix_signal_add

APP_ID = "org.local.HydeSettings"

from hyde_settings.pages.appearance import AppearancePage  # noqa: E402
from hyde_settings.pages.apps import AppsPage  # noqa: E402
from hyde_settings.pages.display import DisplayPage  # noqa: E402
from hyde_settings.pages.keybinds import KeybindsPage  # noqa: E402
from hyde_settings.pages.rules import RulesPage  # noqa: E402

# Page classes in sidebar order; each page task registers its class here.
PAGES = [KeybindsPage, AppsPage, DisplayPage, RulesPage, AppearancePage]


class HydeSettings(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.hypr = Hypr()
        self.saved, self.load_error = store.load()
        if self.load_error:
            # Invalid shapes (e.g. "input": null) must not reach the pages; stay read-only on defaults.
            self.saved = store.default_settings()
        self.pending = copy.deepcopy(self.saved)
        self.hypr_ok = self.hypr.available()
        self.read_only = bool(self.load_error) or not self.hypr_ok
        self.applier = Applier(self.hypr)
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = MainWindow(self, [cls(self) for cls in PAGES])
            self.connect("shutdown", lambda *_args: self.hypr.leave_capture())
            for signum in (signal.SIGINT, signal.SIGTERM):
                unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._on_signal)
        self.window.present()
        self.update_banner()
        self.refresh()

    def _on_signal(self):
        self.quit()
        return GLib.SOURCE_REMOVE

    def refresh(self):
        for page in self.window.pages:
            page.refresh()

    def changed(self):
        self.window.set_pending(store.count_changes(self.saved, self.pending))

    def update_banner(self):
        if self.load_error:
            self.window.show_banner(f"Somente leitura — {self.load_error} (há um settings.json.bak ao lado)")
        elif not self.hypr_ok:
            self.window.show_banner("Somente leitura — o Hyprland não respondeu ao hyprctl")
        elif not hook.has_require():
            self.window.show_banner("O hyprland.lua ainda não carrega o ui.lua", "Adicionar")
        else:
            self.window.hide_banner()

    def add_require(self):
        hook.add_require()
        self.update_banner()
        self.window.toast('require("ui") adicionado ao fim do hyprland.lua')

    def discard(self):
        self.pending = copy.deepcopy(self.saved)
        self.refresh()
        self.changed()

    def apply(self):
        result = self.applier.apply(self.saved, self.pending)
        if not result.ok:
            self.window.error("Não foi possível aplicar", result.error)
            return
        if result.awaiting_confirm:
            self.window.confirm_dangerous(self._keep, self._revert)
            return
        self._committed("Configurações aplicadas")

    def _keep(self):
        self.applier.keep(self.pending)
        self._committed("Configurações mantidas")

    def _revert(self):
        err = self.applier.revert()
        self.refresh()
        self.window.toast(f"Erro ao reverter: {err}" if err else "Configurações revertidas")

    def _committed(self, message):
        self.saved = copy.deepcopy(self.pending)
        self.changed()
        self.refresh()
        self.window.toast(message)
