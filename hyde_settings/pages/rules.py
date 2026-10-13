"""Window rules: per-app opacity, float and idle-inhibit; layer rules shown read-only."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from hyde_settings import rules, store, ui  # noqa: E402
from hyde_settings.pages import Page  # noqa: E402

FLOAT_CHOICES = ("Padrão do HyDE", "Flutuar", "Não flutuar")
FLOAT_VALUES = (None, True, False)
IDLE_CHOICES = ("Padrão", "Nunca suspender", "Não suspender em tela cheia")
IDLE_VALUES = (None, "always", "fullscreen")


class RulesPage(Page):
    key = "rules"
    title = "Regras de janela"
    icon = "preferences-desktop-apps-symbolic"

    def __init__(self, app):
        super().__init__(app)
        self.query = ""
        self.list_group = Adw.PreferencesGroup(title="Suas regras")
        add = Gtk.Button(label="Nova regra", valign=Gtk.Align.CENTER)
        add.add_css_class("suggested-action")
        add.connect("clicked", lambda *_args: self._edit(None))
        self.list_group.set_header_suffix(add)
        self.layer_group = Adw.PreferencesGroup(title="Regras de camada",
                                                description="Somente leitura nesta versão")
        self.prefs.add(self.list_group)
        self.prefs.add(self.layer_group)
        self.rule_widgets = []
        self.layer_widgets = []

    def refresh(self):
        for widget in self.rule_widgets:
            self.list_group.remove(widget)
        for widget in self.layer_widgets:
            self.layer_group.remove(widget)
        self.rule_widgets, self.layer_widgets = [], []
        for index, rule in enumerate(self.app.pending["window_rules"]):
            row = Adw.ActionRow(title=rule["name"], subtitle=rules.summary(rule), use_markup=False)
            row.add_suffix(ui.flat_icon_button("document-edit-symbolic", "Editar", lambda i=index: self._edit(i)))
            row.add_suffix(ui.flat_icon_button("user-trash-symbolic", "Apagar", lambda i=index: self._delete(i)))
            self.list_group.add(row)
            self.rule_widgets.append(row)
        for rule in self.app.pending["layer_rules"]:
            row = Adw.ActionRow(title=rule["name"], subtitle=rule["match"]["namespace"], use_markup=False)
            self.layer_group.add(row)
            self.layer_widgets.append(row)
        self.filter(self.query)

    def filter(self, text):
        self.query = text.lower()
        for row in self.rule_widgets:
            row.set_visible(self.query in f"{row.get_title()} {row.get_subtitle()}".lower())

    def _delete(self, index):
        del self.app.pending["window_rules"][index]
        self.changed()
        self.refresh()

    def _edit(self, index):
        RuleDialog(self.app, index, self._save).present(self.app.window)

    def _save(self, index, rule):
        if index is None:
            self.app.pending["window_rules"].append(rule)
        else:
            self.app.pending["window_rules"][index] = rule
        self.changed()
        self.refresh()


class RuleDialog(Adw.Dialog):
    def __init__(self, app, index, on_save):
        super().__init__(title="Regra de janela", content_width=520)
        self.app, self.index, self.on_save = app, index, on_save
        all_rules = app.pending["window_rules"]
        rule = all_rules[index] if index is not None else {"name": "", "match": {}}
        self.taken = {r["name"] for i, r in enumerate(all_rules) if i != index}
        self.original_match = dict(rule["match"])

        group = Adw.PreferencesGroup()
        self.name = Adw.EntryRow(title="Nome", text=rule["name"])
        self.window_class = Adw.EntryRow(title="Classe (regex)", text=rule["match"].get("class") or "")
        pick = Gtk.MenuButton(icon_name="find-location-symbolic", valign=Gtk.Align.CENTER,
                              tooltip_text="Escolher uma janela aberta")
        pick.add_css_class("flat")
        pick.set_popover(self._clients_popover())
        self.window_class.add_suffix(pick)
        self.title_match = Adw.EntryRow(title="Título (regex, opcional)", text=rule["match"].get("title") or "")
        opacity = rule.get("opacity")
        self.use_opacity = Adw.SwitchRow(title="Definir opacidade", active=opacity is not None)
        self.opacity_rows = []
        values = [*(opacity or [1.0, 0.9]), 1.0][:3]
        for label, value in zip(("Opacidade ativa", "Opacidade inativa", "Opacidade em tela cheia"), values):
            spin = Adw.SpinRow.new_with_range(0.0, 1.0, 0.05)
            spin.set_title(label)
            spin.set_digits(2)
            spin.set_value(value)
            self.opacity_rows.append(spin)
        self.float_row = Adw.ComboRow(title="Flutuar", model=Gtk.StringList.new(FLOAT_CHOICES))
        self.float_row.set_selected(FLOAT_VALUES.index(rule.get("float")))
        self.idle_row = Adw.ComboRow(title="Suspensão de tela", model=Gtk.StringList.new(IDLE_CHOICES))
        self.idle_row.set_selected(IDLE_VALUES.index(rule.get("idle_inhibit")))
        for widget in (self.name, self.window_class, self.title_match, self.use_opacity,
                       *self.opacity_rows, self.float_row, self.idle_row):
            group.add(widget)
        self.use_opacity.connect("notify::active", lambda *_args: self._sync())

        self.warning = Gtk.Label(wrap=True, xalign=0)
        self.warning.add_css_class("warning")
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda *_args: self.close())
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        buttons.append(cancel)
        buttons.append(save)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        body.append(group)
        body.append(self.warning)
        body.append(buttons)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(body)
        self.set_child(view)
        self._sync()

    def _sync(self):
        for spin in self.opacity_rows:
            spin.set_visible(self.use_opacity.get_active())

    def _clients_popover(self):
        listbox = Gtk.ListBox()
        for client in self.app.hypr.clients():
            if not client.get("class"):
                continue
            item = Gtk.ListBoxRow(child=Gtk.Label(label=f"{client['class']} — {client.get('title', '')}", xalign=0,
                                                  margin_start=8, margin_end=8, margin_top=4, margin_bottom=4))
            item.window_class = client["class"]
            listbox.append(item)
        popover = Gtk.Popover(child=Gtk.ScrolledWindow(child=listbox, min_content_height=260, min_content_width=320))

        def activated(_listbox, item):
            self.window_class.set_text(rules.class_regex(item.window_class))
            if not self.name.get_text().strip():
                self.name.set_text(rules.unique_name(item.window_class, self.taken))
            popover.popdown()

        listbox.connect("row-activated", activated)
        return popover

    def _save(self, *_args):
        match = dict(self.original_match)
        for key, row in (("class", self.window_class), ("title", self.title_match)):
            text = row.get_text().strip()
            if text:
                match[key] = text
            else:
                match.pop(key, None)
        rule = {
            "name": self.name.get_text().strip(),
            "match": match,
            "opacity": [round(s.get_value(), 2) for s in self.opacity_rows] if self.use_opacity.get_active() else None,
            "float": FLOAT_VALUES[self.float_row.get_selected()],
            "idle_inhibit": IDLE_VALUES[self.idle_row.get_selected()],
        }
        errors = store.window_rule_errors(rule, self.taken)
        if errors:
            self.warning.set_label("\n".join(errors))
            return
        self.on_save(self.index, rule)
        self.close()
