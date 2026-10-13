from hyde_settings import binds, store


def live(modmask, key, description, submap=""):
    return {"modmask": modmask, "key": key, "description": description, "submap": submap, "dispatcher": "__lua"}


LIVE = [
    live(64, "Q", "[Window Management] close focused window"),
    live(64, "C", "[Launcher|Apps] text editor"),
    live(64, "M", "[Window Management] toggle maximize"),
    live(0, "F10", "[Hardware Controls|Audio] un/mute output"),
    live(64, "K", "manual thing"),
    live(0, "Escape", "[hyde-settings] leave key capture", submap="hs_capture"),
]


def settings():
    s = store.default_settings()
    s["apps"]["editor"]["command"] = "code"
    s["binds"] = [
        {"key": "SUPER + M", "action": {"type": "dispatch", "name": "maximize"}, "description": "[Window Management] maximize"},
        {"key": "SUPER + G", "action": {"type": "unbind"}},
        {"key": "SUPER + J", "action": {"type": "exec", "command": "foo"}},
    ]
    return s


def test_live_combo_and_text_helpers():
    assert binds.live_combo(live(64 | 1, "q", "")) == "SUPER + SHIFT + Q"
    assert binds.category("[Hardware Controls|Audio] mute") == "Hardware Controls"
    assert binds.category("no brackets") == "Outros"
    assert binds.label("[Window Management] close focused window") == "close focused window"
    assert binds.label("") == "(sem descrição)"


def test_action_summary():
    assert binds.action_summary({"type": "exec", "command": "foo"}) == "foo"
    assert binds.action_summary({"type": "dispatch", "name": "workspace", "args": {"n": 3}}) == "Ir para o workspace N (3)"
    assert binds.action_summary({"type": "unbind"}) == "(removido)"


def test_scan_manual_skips_comments_and_bad_combos(tmp_path):
    f = tmp_path / "keybinds.lua"
    f.write_text('--   hl.bind("SUPER + SPACE", x)\nhl.bind("SUPER + K", x)\nhl.bind("HYPER + Z", x)\n')
    assert binds.scan_manual([f, tmp_path / "missing.lua"]) == {(64, "k")}


def test_manual_files_excludes_generated_ui(tmp_path):
    for name in ("hyprland.lua", "ui.lua", "legacy.lua", "notes.txt"):
        (tmp_path / name).write_text("")
    assert [p.name for p in binds.manual_files(tmp_path)] == ["hyprland.lua", "legacy.lua"]


def test_build_rows_tags_origins():
    rows = {r.combo: r for r in binds.build_rows(LIVE, settings(), {(64, "k")})}
    assert rows["SUPER + Q"].origin == "hyde"
    assert rows["SUPER + C"].origin == "yours" and rows["SUPER + C"].role == "editor"
    assert rows["SUPER + M"].origin == "yours" and rows["SUPER + M"].bind_index == 0
    assert rows["SUPER + M"].label == "maximize"  # from settings, not the live description
    assert rows["SUPER + G"].origin == "removed" and rows["SUPER + G"].bind_index == 1
    assert rows["SUPER + J"].origin == "yours" and rows["SUPER + J"].label == "foo"  # pending, not live yet
    assert rows["SUPER + K"].origin == "manual"
    assert "Escape" not in rows  # submap binds are hidden


def test_build_rows_sorted_by_category_then_combo():
    rows = binds.build_rows(LIVE, settings(), set())
    keys = [(r.category.lower(), r.combo.lower()) for r in rows]
    assert keys == sorted(keys)


def test_conflicts():
    rows = binds.build_rows(LIVE, settings(), set())
    assert [r.origin for r in binds.conflicts("super + q", rows)] == ["hyde"]
    assert binds.conflicts("SUPER + G", rows) == []  # removed rows never conflict
    editing = next(r for r in rows if r.combo == "SUPER + M")
    assert binds.conflicts("SUPER + M", rows, editing=editing) == []


def test_combo_from_gtk():
    assert binds.combo_from_gtk("q", {"SUPER"}) == "SUPER + Q"
    assert binds.combo_from_gtk("1", {"SHIFT", "SUPER"}) == "SUPER + SHIFT + 1"
    assert binds.combo_from_gtk("F10", set()) == "F10"


def test_combo_from_gtk_ignores_bare_modifiers():
    for name in ("Super_L", "Control_R", "Shift_L", "Alt_L", "ISO_Level3_Shift"):
        assert binds.combo_from_gtk(name, set()) is None
        assert binds.combo_from_gtk(name, {"SUPER"}) is None
    assert binds.combo_from_gtk(None, {"SUPER"}) is None


def test_command_missing():
    which = {"ls": "/usr/bin/ls", "hyde-shell": "/home/u/.local/bin/hyde-shell"}.get
    assert not binds.command_missing("ls -la", which=which)
    assert not binds.command_missing("hyde-shell logout", which=which)
    assert binds.command_missing("nope --flag", which=which)
    assert binds.command_missing("", which=which)
    assert binds.command_missing('unterminated "quote', which=which)
