from hyde_settings import hook


def test_has_require_detects_active_line_only(tmp_path):
    f = tmp_path / "hyprland.lua"
    f.write_text('require("legacy")\n-- require("ui")\n')
    assert not hook.has_require(f)
    f.write_text('require("legacy")\n  require "ui"\n')
    assert hook.has_require(f)


def test_has_require_missing_file(tmp_path):
    assert not hook.has_require(tmp_path / "nope.lua")


def test_add_require_appends_without_rewriting(tmp_path):
    f = tmp_path / "hyprland.lua"
    f.write_text('hl.config({})\n')
    hook.add_require(f)
    text = f.read_text()
    assert text.startswith('hl.config({})\n')
    assert text.rstrip().endswith('require("ui")')
    assert hook.has_require(f)


def test_default_path_uses_config_home(config_home):
    assert hook.hyprland_lua_path() == config_home / "hypr" / "hyprland.lua"
