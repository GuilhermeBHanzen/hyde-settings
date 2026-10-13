"""Keybinds: every live bind grouped by category, with origin tags, edit, remove and reset."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from hyde_settings import binds, model, store, ui  # noqa: E402
from hyde_settings.pages import Page  # noqa: E402

ORIGIN_LABELS = {"hyde": "HyDE", "yours": "seu", "manual": "manual", "removed": "removido"}
GTK_MODS = (
    ("SUPER", Gdk.ModifierType.SUPER_MASK),
    ("CTRL", Gdk.ModifierType.CONTROL_MASK),
    ("ALT", Gdk.ModifierType.ALT_MASK),
    ("SHIFT", Gdk.ModifierType.SHIFT_MASK),
)
COMBO_TITLE = "Combinação (ex.: SUPER + K)"
CAPTURE_SECONDS = 10


class KeybindsPage(Page):
    key = "keybinds"
    title = "Atalhos"
    icon = "input-keyboard-symbolic"

    def __init__(self, app):
        super().__init__(app)
        self.groups = []
        self.widgets = []  # (group, row_widget, searchable_text)
        self.rows = []
        self.query = ""
        top = Adw.PreferencesGroup(description="Todos os atalhos ativos. Os seus vencem os do HyDE.")
        add = Gtk.Button(label="Novo atalho", valign=Gtk.Align.CENTER)
        add.add_css_class("suggested-action")
        add.connect("clicked", lambda *_args: self._edit(None))
        top.set_header_suffix(add)
        self.prefs.add(top)

    def refresh(self):
        for group in self.groups:
            self.prefs.remove(group)
        self.groups, self.widgets = [], []
        manual = binds.scan_manual(binds.manual_files(store.config_dir() / "hypr"))
        self.rows = binds.build_rows(self.app.hypr.binds(), self.app.pending, manual)
        by_category = {}
        for row in self.rows:
            group = by_category.get(row.category)
            if group is None:
                group = Adw.PreferencesGroup(title=row.category)
                by_category[row.category] = group
                self.prefs.add(group)
                self.groups.append(group)
            widget = self._row_widget(row)
            group.add(widget)
            self.widgets.append((group, widget, f"{row.combo} {row.label}".lower()))
        self.filter(self.query)

    def filter(self, text):
        self.query = text.lower()
        visible = set()
        for group, widget, haystack in self.widgets:
            show = self.query in haystack
            widget.set_visible(show)
            if show:
                visible.add(group)
        for group in self.groups:
            group.set_visible(group in visible)

    def _row_widget(self, row):
        widget = Adw.ActionRow(title=row.combo, subtitle=row.label)
        widget.add_suffix(ui.tag(ORIGIN_LABELS[row.origin]))
        if row.origin == "manual":
            widget.set_tooltip_text("Definido à mão em ~/.config/hypr — edite o arquivo")
        elif row.role is not None:
            widget.set_tooltip_text("Edite em Apps padrão")
        elif row.origin != "removed":
            widget.add_suffix(ui.flat_icon_button("document-edit-symbolic", "Editar", lambda r=row: self._edit(r)))
        if row.origin in ("yours", "removed") and row.role is None:
            widget.add_suffix(ui.reset_button(lambda r=row: self._reset(r)))
        return widget

    def _reset(self, row):
        del self.app.pending["binds"][row.bind_index]
        self.changed()
        self.refresh()

    def _edit(self, row):
        BindDialog(self.app, self.rows, row, self._save, self._remove).present(self.app.window)

    def _save(self, row, entry):
        if row is not None and row.bind_index is not None:
            self.app.pending["binds"][row.bind_index] = entry
        else:
            self.app.pending["binds"].append(entry)
        self.changed()
        self.refresh()

    def _remove(self, row):
        self.app.pending["binds"].append({"key": row.combo, "action": {"type": "unbind"}})
        self.changed()
        self.refresh()


class BindDialog(Adw.Dialog):
    """Create or edit one bind. Capture pauses Hyprland's binds through the hs_capture submap."""

    def __init__(self, app, rows, row, on_save, on_remove):
        super().__init__(title="Atalho", content_width=520)
        self.app, self.rows, self.row = app, rows, row
        self.on_save, self.on_remove = on_save, on_remove
        self.capturing = False
        self._timeout = 0
        existing = app.pending["binds"][row.bind_index] if row is not None and row.bind_index is not None else None

        group = Adw.PreferencesGroup()
        self.combo_entry = Adw.EntryRow(title=COMBO_TITLE, text=row.combo if row else "")
        capture = Gtk.Button(label="Capturar", valign=Gtk.Align.CENTER)
        capture.connect("clicked", self._start_capture)
        self.combo_entry.add_suffix(capture)
        self.action = Adw.ComboRow(title="Ação",
                                   model=Gtk.StringList.new(["Executar comando", *model.DISPATCH_LABELS.values()]))
        self.command = Adw.EntryRow(title="Comando")
        self.command.connect("changed", lambda r: ui.flag_missing(r, r.get_text().strip()))
        self.number = Adw.SpinRow.new_with_range(1, 99, 1)
        self.number.set_title("Workspace")
        self.description = Adw.EntryRow(title="Descrição (ex.: [Launcher] meu app)")
        for widget in (self.combo_entry, self.action, self.command, self.number, self.description):
            group.add(widget)

        self.warning = Gtk.Label(wrap=True, xalign=0)
        self.warning.add_css_class("warning")
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda *_args: self.close())
        buttons.append(cancel)
        if row is not None and row.origin == "hyde":
            remove = Gtk.Button(label="Remover atalho")
            remove.add_css_class("destructive-action")
            remove.connect("clicked", self._remove)
            buttons.append(remove)
        self.save_button = Gtk.Button(label="Salvar")
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self._save)
        buttons.append(self.save_button)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        body.append(group)
        body.append(self.warning)
        body.append(buttons)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(body)
        self.set_child(view)

        if existing is not None:
            action = existing["action"]
            if action["type"] == "dispatch":
                self.action.set_selected(list(model.DISPATCH_LABELS).index(action["name"]) + 1)
                if model.DISPATCHERS[action["name"]]:
                    self.number.set_value(action["args"]["n"])
            else:
                self.command.set_text(action.get("command", ""))
            self.description.set_text(existing.get("description") or "")
        elif row is not None:
            self.description.set_text(f"[{row.category}] {row.label}")

        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.connect("closed", lambda *_args: self._stop_capture())
        self.action.connect("notify::selected", lambda *_args: self._sync_visibility())
        self.combo_entry.connect("changed", lambda *_args: self._check())
        self._sync_visibility()
        self._check()

    def _dispatch_name(self):
        index = self.action.get_selected()
        return None if index == 0 else list(model.DISPATCH_LABELS)[index - 1]

    def _sync_visibility(self):
        name = self._dispatch_name()
        self.command.set_visible(name is None)
        self.number.set_visible(name is not None and model.DISPATCHERS[name])

    def _check(self):
        """Validate the combo text; returns the normalized combo or None, updating the warning."""
        text = self.combo_entry.get_text()
        try:
            combo = model.normalize_combo(text)
        except ValueError as exc:
            self.warning.set_label(str(exc) if text else "")
            self.save_button.set_sensitive(False)
            return None
        clashes = binds.conflicts(combo, self.rows, editing=self.row)
        yours = [r for r in clashes if r.origin == "yours"]
        if yours:
            self.warning.set_label(f"{combo} já é usado por outro atalho seu: {yours[0].label}")
            self.save_button.set_sensitive(False)
            return None
        self.warning.set_label("; ".join(f"{combo} já faz: {r.label} — será substituído" for r in clashes))
        self.save_button.set_sensitive(True)
        return combo

    def _start_capture(self, *_args):
        err = self.app.hypr.enter_capture()
        if err:
            self.warning.set_label(f"Não foi possível pausar os atalhos: {err}")
            return
        self.capturing = True
        self.combo_entry.set_text("")
        self.combo_entry.set_title("Pressione a combinação… (Esc cancela)")
        self._timeout = GLib.timeout_add_seconds(CAPTURE_SECONDS, self._capture_timeout)

    def _capture_timeout(self):
        self._timeout = 0
        self._stop_capture()
        return GLib.SOURCE_REMOVE

    def _stop_capture(self):
        if not self.capturing:
            return
        self.capturing = False
        if self._timeout:
            GLib.source_remove(self._timeout)
            self._timeout = 0
        self.app.hypr.leave_capture()
        self.combo_entry.set_title(COMBO_TITLE)

    def _on_key(self, _controller, keyval, keycode, state):
        if not self.capturing:
            return False
        mods = {name for name, mask in GTK_MODS if state & mask}
        ok, base, *_rest = self.get_display().translate_key(keycode, 0, 0)  # unshifted keyval
        name = Gdk.keyval_name(base if ok else keyval)
        if name == "Escape" and not mods:
            self._stop_capture()
            return True
        combo = binds.combo_from_gtk(name, mods)
        if combo is None:
            return True
        self.combo_entry.set_text(combo)
        self._stop_capture()
        self._check()
        return True

    def _save(self, *_args):
        combo = self._check()
        if combo is None:
            return
        name = self._dispatch_name()
        if name is None:
            command = self.command.get_text().strip()
            if not command:
                self.warning.set_label("Informe o comando")
                return
            action = {"type": "exec", "command": command}
        else:
            action = {"type": "dispatch", "name": name}
            if model.DISPATCHERS[name]:
                action["args"] = {"n": int(self.number.get_value())}
        self.on_save(self.row, {"key": combo, "action": action,
                                "description": self.description.get_text().strip() or None})
        self.close()

    def _remove(self, *_args):
        self.on_remove(self.row)
        self.close()
