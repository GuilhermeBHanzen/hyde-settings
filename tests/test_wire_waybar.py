import wire_waybar

LAYOUT = '''{
    "modules-right": [
            "custom/tlpinfo",
            "custom/vaio-center",
            "cpu"
    ]
}
'''


def test_wire_inserts_after_vaio_center_once():
    wired = wire_waybar.wire(LAYOUT)
    assert '"custom/vaio-center",\n            "custom/hyde-settings",\n            "cpu"' in wired
    assert wire_waybar.wire(wired) is None


def test_wire_without_anchor_returns_none():
    assert wire_waybar.wire('{"modules-right": ["cpu"]}') is None


def test_main_edits_file(tmp_path):
    layout = tmp_path / "gladius.jsonc"
    layout.write_text(LAYOUT)
    assert wire_waybar.main(["wire_waybar.py", str(layout)]) == 0
    assert '"custom/hyde-settings"' in layout.read_text()
    assert wire_waybar.main(["wire_waybar.py", str(layout)]) == 0
    assert layout.read_text().count('"custom/hyde-settings"') == 1
