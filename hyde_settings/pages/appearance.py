"""Appearance: global opacity, gaps, border, rounding and blur; each shows the live value and resets to HyDE."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # noqa: E402

from hyde_settings import ui  # noqa: E402
from hyde_settings.pages import Page  # noqa: E402

# (path inside settings["appearance"], title, lo, hi, step, digits, hyprctl option)
SPINS = (
    (("active_opacity",), "Opacidade da janela ativa", 0.0, 1.0, 0.05, 2, "decoration:active_opacity"),
    (("inactive_opacity",), "Opacidade das janelas inativas", 0.0, 1.0, 0.05, 2, "decoration:inactive_opacity"),
    (("gaps_in",), "Espaço entre janelas", 0, 100, 1, 0, "general:gaps_in"),
    (("gaps_out",), "Margem da tela", 0, 200, 1, 0, "general:gaps_out"),
    (("border_size",), "Espessura da borda", 0, 20, 1, 0, "general:border_size"),
    (("rounding",), "Arredondamento", 0, 50, 1, 0, "decoration:rounding"),
    (("blur", "size"), "Blur: tamanho", 1, 50, 1, 0, "decoration:blur:size"),
    (("blur", "passes"), "Blur: passes", 1, 10, 1, 0, "decoration:blur:passes"),
)


class AppearancePage(Page):
    key = "appearance"
    title = "Aparência"
    icon = "preferences-desktop-appearance-symbolic"

    def __init__(self, app):
        super().__init__(app)
        group = Adw.PreferencesGroup(title="Janelas", description="Sem valor seu = valor do HyDE")
        self.spins = []
        for path, title, lo, hi, step, digits, option in SPINS:
            row = Adw.SpinRow.new_with_range(lo, hi, step)
            row.set_title(title)
            row.set_digits(digits)
            row.connect("notify::value", lambda r, _p, p=path, d=digits: self._set(p, self._value(r, d)))
            row.add_suffix(ui.reset_button(lambda p=path: self._reset(p)))
            group.add(row)
            self.spins.append((row, path, option))
        self.blur = Adw.SwitchRow(title="Blur")
        self.blur.connect("notify::active", lambda r, _p: self._set(("blur", "enabled"), r.get_active()))
        self.blur.add_suffix(ui.reset_button(lambda: self._reset(("blur", "enabled"))))
        group.add(self.blur)
        self.prefs.add(group)

    @staticmethod
    def _value(row, digits):
        return int(row.get_value()) if digits == 0 else round(row.get_value(), digits)

    def _get(self, path):
        node = self.app.pending["appearance"]
        for key in path:
            node = node[key]
        return node

    def _put(self, path, value):
        node = self.app.pending["appearance"]
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    def _set(self, path, value):
        if self._syncing:
            return
        self._put(path, value)
        self.changed()

    def _reset(self, path):
        self._put(path, None)
        self.changed()
        self.refresh()

    def refresh(self):
        hypr = self.app.hypr
        with self.syncing():
            for row, path, option in self.spins:
                live = hypr.option(option)
                mine = self._get(path)
                row.set_value(mine if mine is not None else (live or 0))
                row.set_subtitle(f"Atual: {live}" + (" · seu valor" if mine is not None else " · padrão do HyDE"))
            mine = self._get(("blur", "enabled"))
            live = hypr.option("decoration:blur:enabled")
            self.blur.set_active(mine if mine is not None else bool(live))
            self.blur.set_subtitle("seu valor" if mine is not None else "padrão do HyDE")
