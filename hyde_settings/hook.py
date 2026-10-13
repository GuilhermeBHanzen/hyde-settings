"""The single line in the user's hyprland.lua that loads the generated ui.lua."""
import re
from pathlib import Path

from hyde_settings import store

_REQUIRE_RE = re.compile(r"""^\s*require\s*\(?\s*["']ui["']\s*\)?\s*$""", re.MULTILINE)
_BLOCK = '\n-- Settings managed by hyde-settings (loaded last, overrides everything above).\nrequire("ui")\n'


def hyprland_lua_path():
    return store.config_dir() / "hypr" / "hyprland.lua"


def has_require(path=None):
    try:
        return bool(_REQUIRE_RE.search(Path(path or hyprland_lua_path()).read_text()))
    except OSError:
        return False


def add_require(path=None):
    """Append the require block; never rewrites existing content."""
    with Path(path or hyprland_lua_path()).open("a") as handle:
        handle.write(_BLOCK)
