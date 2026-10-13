"""Monitor (mode, scale, position) and input (layout, pointer). Monitor and layout changes are dangerous."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from hyde_settings import model, ui  # noqa: E402
from hyde_settings.pages import Page  # noqa: E402


def _live_mode(mon):
    return f"{mon['width']}x{mon['height']}@{mon['refreshRate']:.2f}"


class DisplayPage(Page):
    key = "display"
    title = "Monitor e entrada"
    icon = "video-display-symbolic"

    def __init__(self, app):
        super().__init__(app)
        self.monitor_groups = []
        self.input_group = Adw.PreferencesGroup(title="Teclado e mouse",
                                                description="Mudar o layout pede confirmação (15 s)")
        self.kb_layout = Adw.EntryRow(title="Layout do teclado (ex.: br, us)")
        self.kb_variant = Adw.EntryRow(title="Variante do layout (opcional)")
        self.sensitivity = Adw.SpinRow.new_with_range(-1.0, 1.0, 0.05)
        self.sensitivity.set_title("Sensibilidade do mouse")
        self.sensitivity.set_digits(2)
        self.natural = Adw.SwitchRow(title="Scroll natural no touchpad")
        self.numlock = Adw.SwitchRow(title="Num Lock ligado ao iniciar")
        self.kb_layout.connect("changed", lambda r: self._set_input("kb_layout", r.get_text().strip() or None))
        self.kb_variant.connect("changed", lambda r: self._set_input("kb_variant", r.get_text().strip() or None))
        self.sensitivity.connect("notify::value", lambda r, _p: self._set_input("sensitivity", round(r.get_value(), 2)))
        self.natural.connect("notify::active", lambda r, _p: self._set_input("natural_scroll", r.get_active()))
        self.numlock.connect("notify::active", lambda r, _p: self._set_input("numlock_by_default", r.get_active()))
        for key, row in (("kb_layout", self.kb_layout), ("kb_variant", self.kb_variant),
                         ("sensitivity", self.sensitivity), ("natural_scroll", self.natural),
                         ("numlock_by_default", self.numlock)):
            row.add_suffix(ui.reset_button(lambda k=key: self._reset_input(k)))
            self.input_group.add(row)
        self.prefs.add(self.input_group)

    def _set_input(self, key, value):
        if self._syncing:
            return
        self.app.pending["input"][key] = value
        self.changed()

    def _reset_input(self, key):
        self.app.pending["input"][key] = None
        self.changed()
        self.refresh()

    def _monitor_entry(self, mon):
        for entry in self.app.pending["monitors"]:
            if entry["output"] == mon["name"]:
                return entry
        entry = {"output": mon["name"], "mode": _live_mode(mon),
                 "position": f"{mon['x']}x{mon['y']}", "scale": float(mon["scale"])}
        self.app.pending["monitors"].append(entry)
        return entry

    def _set_monitor(self, mon, key, value):
        if self._syncing:
            return
        self._monitor_entry(mon)[key] = value
        self.changed()

    def _reset_monitor(self, name):
        self.app.pending["monitors"] = [m for m in self.app.pending["monitors"] if m["output"] != name]
        self.changed()
        self.refresh()

    def _monitor_group(self, mon):
        saved = next((m for m in self.app.pending["monitors"] if m["output"] == mon["name"]), None)
        group = Adw.PreferencesGroup(title=f"Monitor {mon['name']}",
                                     description="Mudanças aqui pedem confirmação (15 s)")
        group.set_header_suffix(ui.reset_button(lambda n=mon["name"]: self._reset_monitor(n)))
        modes = [m.removesuffix("Hz") for m in mon.get("availableModes", [])]
        mode_row = Adw.ComboRow(title="Resolução e taxa", model=Gtk.StringList.new(modes))
        current = saved["mode"] if saved else _live_mode(mon)
        match = next((i for i, m in enumerate(modes) if model.mode_matches(current, m)), None)
        if match is not None:
            mode_row.set_selected(match)
        mode_row.connect("notify::selected",
                         lambda r, _p: self._set_monitor(mon, "mode", modes[r.get_selected()]))
        scale_row = Adw.SpinRow.new_with_range(0.25, 4.0, 0.05)
        scale_row.set_title("Escala")
        scale_row.set_subtitle("Comuns: 1.0 · 1.25 · 1.5 · 2.0")
        scale_row.set_digits(2)
        scale_row.set_value(saved["scale"] if saved else float(mon["scale"]))
        scale_row.connect("notify::value", lambda r, _p: self._set_monitor(mon, "scale", round(r.get_value(), 2)))
        position_row = Adw.EntryRow(title="Posição (auto ou XxY)",
                                    text=saved["position"] if saved else "auto")
        position_row.connect("changed", lambda r: self._set_monitor(mon, "position", r.get_text().strip()))
        for row in (mode_row, scale_row, position_row):
            group.add(row)
        return group

    def refresh(self):
        with self.syncing():
            for group in self.monitor_groups:
                self.prefs.remove(group)
            self.prefs.remove(self.input_group)
            self.monitor_groups = [self._monitor_group(mon) for mon in self.app.hypr.monitors()]
            for group in self.monitor_groups:
                self.prefs.add(group)
            self.prefs.add(self.input_group)

            inp = self.app.pending["input"]
            hypr = self.app.hypr
            self.kb_layout.set_text(inp["kb_layout"] or "")
            self.kb_layout.set_tooltip_text(f"Atual: {hypr.option('input:kb_layout') or ''}")
            self.kb_variant.set_text(inp["kb_variant"] or "")
            sens = inp["sensitivity"] if inp["sensitivity"] is not None else hypr.option("input:sensitivity")
            self.sensitivity.set_value(sens or 0.0)
            natural = inp["natural_scroll"]
            if natural is None:
                natural = bool(hypr.option("input:touchpad:natural_scroll"))
            self.natural.set_active(natural)
            numlock = inp["numlock_by_default"]
            if numlock is None:
                numlock = bool(hypr.option("input:numlock_by_default"))
            self.numlock.set_active(numlock)
