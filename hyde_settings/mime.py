"""Default applications: query and set MIME handlers through xdg-mime; list installed apps."""
import re

from hyde_settings import proc

FILE_TYPES = (
    ("Texto", ("text/plain",)),
    ("Código", ("text/x-csrc", "text/x-c++src", "text/x-python", "text/x-shellscript",
                "application/json", "text/markdown")),
    ("PDF", ("application/pdf",)),
    ("Imagem", ("image/png", "image/jpeg", "image/webp")),
    ("Vídeo", ("video/mp4", "video/x-matroska", "video/webm")),
    ("Pasta", ("inode/directory",)),
)

_FIELD_CODES = re.compile(r"\s*%[fFuUdDnNickvm]")


def strip_field_codes(cmdline):
    return _FIELD_CODES.sub("", cmdline).replace("%%", "%").strip()


def query_default(mime_type, runner=proc.run):
    out, err = runner(["xdg-mime", "query", "default", mime_type])
    if err is not None:
        return None
    return (out or "").strip() or None


def set_default(desktop_id, mime_types, runner=proc.run):
    _, err = runner(["xdg-mime", "default", desktop_id, *mime_types])
    return err


def installed_apps(mime_type=None):
    """[(desktop_id, display_name, command)] sorted by name. Imports Gio lazily (GTK side only)."""
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    infos = Gio.AppInfo.get_all_for_type(mime_type) if mime_type else Gio.AppInfo.get_all()
    apps = [
        (info.get_id(), info.get_display_name(), strip_field_codes(info.get_commandline() or ""))
        for info in infos
        if info.should_show() and info.get_id()
    ]
    return sorted(apps, key=lambda app: app[1].lower())
