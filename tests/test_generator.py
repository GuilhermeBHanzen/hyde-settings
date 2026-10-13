import shutil
import subprocess

import pytest

from hyde_settings import generator, store

CAPTURE = (
    'hl.define_submap("hs_capture", function()\n'
    '\thl.bind("Escape", hl.dsp.submap("reset"), { description = "[hyde-settings] leave key capture" })\n'
    "end)\n"
)


def assert_valid_lua(text, tmp_path):
    luac = shutil.which("luac")
    if luac is None:
        pytest.skip("luac not installed")
    path = tmp_path / "ui.lua"
    path.write_text(text)
    result = subprocess.run([luac, "-p", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_defaults_generate_header_and_capture_only(tmp_path):
    text = generator.generate(store.default_settings())
    assert text == generator.HEADER + "\n" + CAPTURE
    assert_valid_lua(text, tmp_path)


def test_lua_str_escapes_everything_dangerous():
    assert generator.lua_str('a"b') == '"a\\"b"'
    assert generator.lua_str("a\\b") == '"a\\\\b"'
    assert generator.lua_str("a\nb\tc") == '"a\\nb\\tc"'
    assert generator.lua_str("]] os.exit() --[[") == '"]] os.exit() --[["'
    assert generator.lua_str("\x01") == '"\\001"'


def test_lua_num():
    assert generator.lua_num(1) == "1"
    assert generator.lua_num(0.9) == "0.9"
    assert generator.lua_num(1.0) == "1.0"
    with pytest.raises(TypeError):
        generator.lua_num(True)


def test_monitor_and_config_sections():
    s = store.default_settings()
    s["monitors"] = [{"output": "eDP-1", "mode": "1920x1080@144", "position": "auto", "scale": 1.0}]
    s["input"].update(kb_layout="br", sensitivity=0.7, numlock_by_default=True, natural_scroll=True)
    s["appearance"]["gaps_in"] = 5
    s["appearance"]["blur"]["enabled"] = False
    text = generator.generate(s)
    assert 'hl.monitor({ output = "eDP-1", mode = "1920x1080@144", position = "auto", scale = 1.0 })\n' in text
    assert (
        'hl.config({ input = { kb_layout = "br", sensitivity = 0.7, numlock_by_default = true, '
        "touchpad = { natural_scroll = true } }, general = { gaps_in = 5 }, "
        "decoration = { blur = { enabled = false } } })\n"
    ) in text


def test_apps_and_binds_unbind_before_bind():
    s = store.default_settings()
    s["apps"]["editor"]["command"] = "code"
    s["binds"] = [
        {"key": "super + m", "action": {"type": "dispatch", "name": "maximize"}, "description": "[WM] max"},
        {"key": "SUPER + 2", "action": {"type": "dispatch", "name": "workspace", "args": {"n": 2}}},
        {"key": "SUPER + G", "action": {"type": "unbind"}},
        {"key": "SUPER + Delete", "action": {"type": "exec", "command": 'notify-send "bye"'}},
    ]
    text = generator.generate(s)
    assert (
        'hl.unbind("SUPER + C")\n'
        'hl.bind("SUPER + C", hl.dsp.exec_cmd("code"), { description = "[Launcher|Apps] text editor" })\n'
    ) in text
    assert (
        'hl.unbind("SUPER + M")\n'
        'hl.bind("SUPER + M", hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" }), '
        '{ description = "[WM] max" })\n'
    ) in text
    assert 'hl.bind("SUPER + 2", hl.dsp.focus({ workspace = 2 }), {})\n' in text
    assert 'hl.unbind("SUPER + G")\n' in text and 'hl.bind("SUPER + G"' not in text
    assert 'hl.dsp.exec_cmd("notify-send \\"bye\\"")' in text


def test_window_and_layer_rules():
    s = store.default_settings()
    s["window_rules"] = [
        {"name": "kitty", "match": {"class": "^(kitty)$"}, "opacity": [0.9, 0.8, 1.0], "float": None, "idle_inhibit": None},
        {"name": "mpv", "match": {"class": "^(mpv)$"}, "opacity": None, "float": True, "idle_inhibit": "fullscreen"},
    ]
    s["layer_rules"] = [{"name": "blur", "match": {"namespace": "^(rofi)$"}, "blur": True, "ignore_alpha": 0}]
    text = generator.generate(s)
    assert 'hl.window_rule({ name = "hs-kitty", match = { class = "^(kitty)$" }, opacity = "0.9 0.8 1.0" })\n' in text
    assert (
        'hl.window_rule({ name = "hs-mpv", match = { class = "^(mpv)$", fullscreen = true }, '
        'float = true, idle_inhibit = "always" })\n'
    ) in text
    assert 'hl.layer_rule({ name = "hs-blur", match = { namespace = "^(rofi)$" }, blur = true, ignore_alpha = 0 })\n' in text


def test_section_order_and_determinism(tmp_path):
    s = store.default_settings()
    s["monitors"] = [{"output": "eDP-1", "mode": "preferred", "position": "auto", "scale": 1.25}]
    s["apps"]["terminal"]["command"] = "kitty"
    s["binds"] = [{"key": "SUPER + K", "action": {"type": "exec", "command": "x"}}]
    s["window_rules"] = [{"name": "a", "match": {"title": "x"}, "float": False}]
    first = generator.generate(s)
    assert first == generator.generate(s)
    order = [first.index(token) for token in ("define_submap", "hl.monitor", "SUPER + T", "SUPER + K", "hl.window_rule")]
    assert order == sorted(order)
    assert_valid_lua(first, tmp_path)


def test_hostile_strings_still_valid_lua(tmp_path):
    s = store.default_settings()
    s["binds"] = [{"key": "SUPER + K", "action": {"type": "exec", "command": 'a"]]\n--[[ \\ \x07'},
                   "description": "é — ç"}]
    assert_valid_lua(generator.generate(s), tmp_path)
