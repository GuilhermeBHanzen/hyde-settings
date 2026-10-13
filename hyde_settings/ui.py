"""GTK helpers shared by every page."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402

from hyde_settings import binds  # noqa: E402


def flat_icon_button(icon, tooltip, callback):
    button = Gtk.Button(icon_name=icon, valign=Gtk.Align.CENTER, tooltip_text=tooltip)
    button.add_css_class("flat")
    button.connect("clicked", lambda *_args: callback())
    return button


def reset_button(callback):
    return flat_icon_button("edit-undo-symbolic", "Voltar ao padrão do HyDE", callback)


def tag(text):
    label = Gtk.Label(label=text, valign=Gtk.Align.CENTER)
    label.add_css_class("caption")
    label.add_css_class("dim-label")
    return label


def flag_missing(row, command):
    """Yellow warning on an entry row whose command is not on PATH; saving stays allowed."""
    if command and binds.command_missing(command):
        row.add_css_class("warning")
        row.set_tooltip_text("Comando não encontrado no PATH")
    else:
        row.remove_css_class("warning")
        row.set_tooltip_text(None)
