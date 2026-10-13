import json
import os

import pytest

from hyde_settings import store


def valid():
    s = store.default_settings()
    s["monitors"] = [{"output": "eDP-1", "mode": "1920x1080@144", "position": "auto", "scale": 1.0}]
    s["input"].update(kb_layout="br", sensitivity=0.7, numlock_by_default=True, natural_scroll=True)
    s["apps"]["editor"]["command"] = "code"
    s["binds"] = [
        {"key": "SUPER + M", "action": {"type": "dispatch", "name": "maximize"}, "description": "[WM] max"},
        {"key": "SUPER + G", "action": {"type": "unbind"}},
    ]
    s["window_rules"] = [{"name": "kitty", "match": {"class": "^(kitty)$"}, "opacity": [0.9, 0.8, 1.0],
                          "float": None, "idle_inhibit": None}]
    s["layer_rules"] = [{"name": "blur", "match": {"namespace": "^(rofi)$"}, "blur": True, "ignore_alpha": 0}]
    return s


def test_default_settings_are_valid():
    assert store.validate(store.default_settings()) == []


def test_valid_example_passes():
    assert store.validate(valid()) == []


def test_load_missing_file_returns_defaults(config_home):
    settings, error = store.load()
    assert error is None
    assert settings == store.default_settings()


def test_save_then_load_round_trips(config_home):
    store.save(valid())
    settings, error = store.load()
    assert error is None
    assert settings == valid()


def test_load_fills_missing_sections(config_home):
    path = store.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 1, "input": {"kb_layout": "br"}}))
    settings, error = store.load()
    assert error is None
    assert settings["input"]["kb_layout"] == "br"
    assert settings["input"]["sensitivity"] is None
    assert settings["apps"]["terminal"]["key"] == "SUPER + T"
    assert settings["window_rules"] == []


def test_load_invalid_json_is_read_only_defaults(config_home):
    path = store.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text("{ not json")
    settings, error = store.load()
    assert "JSON inválido" in error
    assert settings == store.default_settings()


def test_load_unknown_version_is_an_error(config_home):
    path = store.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 2}))
    _, error = store.load()
    assert "versão" in error


def test_load_invalid_value_names_the_field(config_home):
    bad = valid()
    bad["monitors"][0]["scale"] = 0
    path = store.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(bad))
    settings, error = store.load()
    assert "escala" in error
    assert settings["monitors"][0]["scale"] == 0


def test_save_rejects_invalid_settings(config_home):
    bad = valid()
    bad["appearance"]["active_opacity"] = 1.5
    with pytest.raises(store.SettingsError):
        store.save(bad)
    assert not store.settings_path().exists()


def test_save_keeps_previous_file_as_bak(config_home):
    store.save(store.default_settings())
    store.save(valid())
    bak = store.settings_path().with_name("settings.json.bak")
    assert json.loads(bak.read_text()) == store.default_settings()


def test_write_atomic_leaves_original_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "f.txt"
    target.write_text("old")

    def boom(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.write_atomic(target, "new")
    assert target.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["f.txt"]


def test_validate_rejects_duplicate_combo_across_apps_and_binds():
    s = valid()
    s["binds"].append({"key": "super + c", "action": {"type": "exec", "command": "gedit"}})
    errors = store.validate(s)
    assert any("SUPER + C" in e and "duas vezes" in e for e in errors)


def test_validate_bad_combo_and_dispatcher():
    s = valid()
    s["binds"] = [{"key": "HYPER + K", "action": {"type": "dispatch", "name": "teleport"}}]
    errors = store.validate(s)
    assert any("modificador desconhecido" in e for e in errors)
    assert any("ação desconhecida" in e for e in errors)


def test_validate_workspace_number_required():
    s = valid()
    s["binds"] = [{"key": "SUPER + 1", "action": {"type": "dispatch", "name": "workspace", "args": {}}}]
    assert any("workspace" in e for e in store.validate(s))


def test_window_rule_errors():
    taken = {"kitty"}
    assert store.window_rule_errors({"name": "kitty", "match": {"class": "x"}, "float": True}, taken)
    assert store.window_rule_errors({"name": "new", "match": {}, "float": True}, taken)
    assert store.window_rule_errors({"name": "new", "match": {"class": "("}, "float": True}, taken)
    assert store.window_rule_errors({"name": "new", "match": {"class": "x"}}, taken)
    assert store.window_rule_errors({"name": "new", "match": {"class": "x"}, "opacity": [2, 1]}, taken)
    assert store.window_rule_errors({"name": "new", "match": {"class": "x"}, "idle_inhibit": "fullscreen"}, taken) == []


def test_count_changes_counts_leaves():
    a = valid()
    b = valid()
    assert store.count_changes(a, b) == 0
    b["input"]["kb_layout"] = "us"
    b["monitors"][0]["scale"] = 1.5
    b["window_rules"].append({"name": "x", "match": {"class": "x"}, "float": True})
    assert store.count_changes(a, b) == 3
