"""Main window: section list on the left, pages on the right, Apply/Discard and search on top."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from hyde_settings import apply  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, pages):
        super().__init__(application=app, title="HyDE Settings", default_width=1000, default_height=700)
        self.app = app
        self.pages = pages
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True, hexpand=True)
        for page in pages:
            self.stack.add_named(page, page.key)

        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.sidebar.add_css_class("navigation-sidebar")
        for page in pages:
            box = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
            box.append(Gtk.Image(icon_name=page.icon))
            box.append(Gtk.Label(label=page.title, xalign=0))
            row = Gtk.ListBoxRow(child=box)
            row.page_key = page.key
            self.sidebar.append(row)
        self.sidebar.connect("row-selected", self._on_row_selected)
        side_view = Adw.ToolbarView()
        side_view.add_top_bar(Adw.HeaderBar(show_title=False))
        side_view.set_content(self.sidebar)

        self.search = Gtk.SearchEntry(placeholder_text="Buscar…", width_chars=30)
        self.search.connect("search-changed", self._on_search)
        self.apply_button = Gtk.Button(label="Aplicar")
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.connect("clicked", lambda *_args: app.apply())
        self.discard_button = Gtk.Button(label="Descartar")
        self.discard_button.connect("clicked", lambda *_args: app.discard())
        header = Adw.HeaderBar()
        header.set_title_widget(self.search)
        header.pack_end(self.apply_button)
        header.pack_end(self.discard_button)

        self.banner = Adw.Banner()
        self.banner.set_use_markup(False)
        self.banner.connect("button-clicked", lambda *_args: app.add_require())
        self.toasts = Adw.ToastOverlay(child=self.stack, vexpand=True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self.banner)
        body.append(self.toasts)
        content_view = Adw.ToolbarView()
        content_view.add_top_bar(header)
        content_view.set_content(body)

        split = Adw.NavigationSplitView(
            sidebar=Adw.NavigationPage(child=side_view, title="HyDE Settings"),
            content=Adw.NavigationPage(child=content_view, title="Configurações"),
        )
        self.set_content(split)
        first = self.sidebar.get_row_at_index(0)
        if first is not None:
            self.sidebar.select_row(first)
        self.set_pending(0)

    def _visible_page(self):
        return self.stack.get_visible_child()

    def _on_search(self, entry):
        page = self._visible_page()
        if page is not None:
            page.filter(entry.get_text())

    def _on_row_selected(self, _listbox, row):
        if row is None:
            return
        self.stack.set_visible_child_name(row.page_key)
        page = self._visible_page()
        page.refresh()
        page.filter(self.search.get_text())

    def set_pending(self, count):
        self.apply_button.set_label(f"Aplicar ({count})" if count else "Aplicar")
        self.apply_button.set_sensitive(count > 0 and not self.app.read_only)
        self.discard_button.set_sensitive(count > 0)

    def show_banner(self, title, button=None):
        self.banner.set_title(title)
        self.banner.set_button_label(button)
        self.banner.set_revealed(True)

    def hide_banner(self):
        self.banner.set_revealed(False)

    def toast(self, text, undo=None):
        toast = Adw.Toast(title=text, timeout=4)
        toast.set_use_markup(False)
        if undo is not None:
            toast.set_button_label("Desfazer")
            toast.connect("button-clicked", lambda *_args: undo())
        self.toasts.add_toast(toast)

    def error(self, heading, body):
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.present(self)

    def confirm_dangerous(self, on_keep, on_revert):
        """'Keep these settings?' with a countdown; timeout or closing means revert."""
        state = {"left": apply.REVERT_SECONDS, "done": False, "source": 0}
        dialog = Adw.AlertDialog(heading="Manter essas configurações?",
                                 body=f"Revertendo em {state['left']} s…")
        dialog.add_response("revert", "Reverter")
        dialog.add_response("keep", "Manter")
        dialog.set_response_appearance("keep", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("revert")
        dialog.set_close_response("revert")

        def finish(response):
            if state["done"]:
                return
            state["done"] = True
            if state["source"]:
                GLib.source_remove(state["source"])
                state["source"] = 0
            (on_keep if response == "keep" else on_revert)()

        def tick():
            state["left"] -= 1
            if state["left"] <= 0:
                state["source"] = 0
                finish("revert")
                dialog.force_close()
                return GLib.SOURCE_REMOVE
            dialog.set_body(f"Revertendo em {state['left']} s…")
            return GLib.SOURCE_CONTINUE

        dialog.connect("response", lambda _dialog, response: finish(response))
        state["source"] = GLib.timeout_add(1000, tick)
        dialog.present(self)
