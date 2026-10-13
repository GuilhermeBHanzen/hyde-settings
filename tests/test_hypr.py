import json

from hyde_settings.hypr import Hypr

BIND_Q = {"locked": False, "mouse": False, "release": False, "repeat": False, "longPress": False,
          "non_consuming": False, "auto_consuming": False, "has_description": True, "modmask": 64,
          "submap": "", "submap_universal": "false", "key": "Q", "keycode": 0, "catch_all": False,
          "description": "[Window Management] close focused window", "allow_input_capture": False,
          "dispatcher": "__lua", "arg": "19"}
MONITOR = {"name": "eDP-1", "width": 1920, "height": 1080, "refreshRate": 144.002, "scale": 1, "x": 0, "y": 0,
           "availableModes": ["1920x1080@144.00Hz", "1920x1080@60.02Hz"]}


def j(value):
    return json.dumps(value), None


def test_binds_monitors_clients(fake_runner):
    runner = fake_runner({
        ("hyprctl", "binds", "-j"): j([BIND_Q]),
        ("hyprctl", "monitors", "-j"): j([MONITOR]),
        ("hyprctl", "clients", "-j"): j([{"class": "kitty", "title": "zsh"}]),
    })
    hypr = Hypr(runner)
    assert hypr.binds() == [BIND_Q]
    assert hypr.monitors()[0]["availableModes"][0] == "1920x1080@144.00Hz"
    assert hypr.clients() == [{"class": "kitty", "title": "zsh"}]


def test_option_decodes_every_type(fake_runner):
    runner = fake_runner({
        ("hyprctl", "getoption", "general:border_size", "-j"): j({"option": "x", "int": 2, "set": True}),
        ("hyprctl", "getoption", "input:sensitivity", "-j"): j({"option": "x", "float": 0.7, "set": True}),
        ("hyprctl", "getoption", "decoration:blur:enabled", "-j"): j({"option": "x", "bool": True, "set": True}),
        ("hyprctl", "getoption", "input:kb_variant", "-j"): j({"option": "x", "str": "[[EMPTY]]", "set": False}),
        ("hyprctl", "getoption", "input:kb_layout", "-j"): j({"option": "x", "str": "br", "set": True}),
        ("hyprctl", "getoption", "general:gaps_in", "-j"): j({"option": "x", "css": "3 3 3 3", "set": True}),
    })
    hypr = Hypr(runner)
    assert hypr.option("general:border_size") == 2
    assert hypr.option("input:sensitivity") == 0.7
    assert hypr.option("decoration:blur:enabled") is True
    assert hypr.option("input:kb_variant") == ""
    assert hypr.option("input:kb_layout") == "br"
    assert hypr.option("general:gaps_in") == 3


def test_config_errors_filters_blank_entries(fake_runner):
    ok = Hypr(fake_runner({("hyprctl", "configerrors", "-j"): j([""])}))
    assert ok.config_errors() == []
    bad = Hypr(fake_runner({("hyprctl", "configerrors", "-j"): j(["ui.lua:3: unknown field"])}))
    assert bad.config_errors() == ["ui.lua:3: unknown field"]


def test_dispatch_uses_lua_and_reports_error_text(fake_runner):
    runner = fake_runner({
        ("hyprctl", "dispatch", 'hl.dsp.submap("hs_capture")'): ("ok\n", None),
        ("hyprctl", "dispatch", 'hl.dsp.submap("reset")'): ("error: something\n", None),
    })
    hypr = Hypr(runner)
    assert hypr.enter_capture() is None
    assert hypr.leave_capture() == "error: something"


def test_hyprctl_failure_degrades(fake_runner):
    failing = {
        ("hyprctl", name, "-j"): (None, "Couldn't connect to the Hyprland socket")
        for name in ("version", "binds", "monitors", "clients", "configerrors")
    }
    failing[("hyprctl", "getoption", "general:gaps_in", "-j")] = (None, "no socket")
    failing[("hyprctl", "reload")] = (None, "no socket")
    hypr = Hypr(fake_runner(failing))
    assert hypr.available() is False
    assert hypr.binds() == [] and hypr.monitors() == [] and hypr.clients() == []
    assert hypr.option("general:gaps_in") is None
    assert hypr.reload() == "no socket"
    assert hypr.config_errors() == ["hyprctl configerrors: Couldn't connect to the Hyprland socket"]


def test_invalid_json_is_treated_as_failure(fake_runner):
    hypr = Hypr(fake_runner({("hyprctl", "binds", "-j"): ("not json", None)}))
    assert hypr.binds() == []
