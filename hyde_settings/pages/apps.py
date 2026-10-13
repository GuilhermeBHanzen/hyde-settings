"""Default apps: launcher commands for SUPER+C/B/T/E, and 'open files with' MIME defaults."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from hyde_settings import mime, model, ui  # noqa: E402
from hyde_settings.pages import Page  # noqa: E402

ROLE_TITLES = {
    "editor": "Editor de texto",
    "browser": "Navegador",
    "terminal": "Terminal",
    "explorer": "Gerenciador de arquivos",
}


class AppsPage(Page):
    key = "apps"
    title = "Apps padrão"
    icon = "application-x-executable-symbolic"

    def __init__(self, app):
        super().__init__(app)
        self.entries = {}
        launchers = Adw.PreferencesGroup(title="Atalhos de apps", description="Vazio = padrão do HyDE")
        installed = mime.installed_apps()
        for role in model.ROLES:
            row = Adw.EntryRow(title=f"{ROLE_TITLES[role]} ({model.ROLE_KEYS[role]})")
            pick = Gtk.MenuButton(icon_name="view-list-symbolic", valign=Gtk.Align.CENTER,
                                  tooltip_text="Escolher um app instalado")
            pick.add_css_class("flat")
            pick.set_popover(self._app_popover(installed, row))
            row.add_suffix(pick)
            row.add_suffix(ui.reset_button(lambda r=row: r.set_text("")))
            row.connect("changed", lambda r, role=role: self._on_command(role, r))
            launchers.add(row)
            self.entries[role] = row
        self.prefs.add(launchers)

        self.mime_rows = []
        files = Adw.PreferencesGroup(title="Abrir arquivos com",
                                     description="Aplicado na hora, sem precisar de Aplicar")
        for title, types in mime.FILE_TYPES:
            choices = mime.installed_apps(types[0])
            row = Adw.ComboRow(title=title, model=Gtk.StringList.new([name for _id, name, _cmd in choices]))
            row.choices, row.mime_types = choices, types
            row.connect("notify::selected", self._on_mime)
            files.add(row)
            self.mime_rows.append(row)
        self.prefs.add(files)

    def _app_popover(self, installed, entry_row):
        listbox = Gtk.ListBox()
        for _id, name, command in installed:
            item = Gtk.ListBoxRow(child=Gtk.Label(label=name, xalign=0, margin_start=8, margin_end=8,
                                                  margin_top=4, margin_bottom=4))
            item.command = command
            listbox.append(item)
        popover = Gtk.Popover(child=Gtk.ScrolledWindow(child=listbox, min_content_height=320, min_content_width=280))

        def activated(_listbox, item):
            entry_row.set_text(item.command)
            popover.popdown()

        listbox.connect("row-activated", activated)
        return popover

    def _on_command(self, role, row):
        text = row.get_text().strip()
        ui.flag_missing(row, text)
        if self._syncing:
            return
        self.app.pending["apps"][role]["command"] = text or None
        self.changed()

    def _on_mime(self, row, _pspec):
        index = row.get_selected()
        if self._syncing or index == Gtk.INVALID_LIST_POSITION:
            return
        desktop_id, name, _cmd = row.choices[index]
        previous = mime.query_default(row.mime_types[0])
        if previous == desktop_id:
            return
        err = mime.set_default(desktop_id, row.mime_types)
        if err:
            self.app.window.toast(f"xdg-mime falhou: {err}")
            self.refresh()
            return

        def undo():
            err = mime.set_default(previous, row.mime_types)
            if err:
                self.app.window.toast(f"xdg-mime falhou ao desfazer: {err}")
            self.refresh()

        self.app.window.toast(f"{row.get_title()}: {name}", undo=undo if previous else None)

    def refresh(self):
        with self.syncing():
            for role, row in self.entries.items():
                row.set_text(self.app.pending["apps"][role]["command"] or "")
            for row in self.mime_rows:
                current = mime.query_default(row.mime_types[0])
                ids = [choice[0] for choice in row.choices]
                row.set_selected(ids.index(current) if current in ids else Gtk.INVALID_LIST_POSITION)
