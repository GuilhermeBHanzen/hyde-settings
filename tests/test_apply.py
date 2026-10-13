import copy

import pytest

from hyde_settings import apply, generator, store


class FakeHypr:
    def __init__(self, reload_error=None, errors=None):
        self.reload_error = reload_error
        self.errors = list(errors or [])
        self.reloads = 0

    def reload(self):
        self.reloads += 1
        return self.reload_error

    def config_errors(self):
        return self.errors


@pytest.fixture
def paths(config_home):
    return config_home / "hypr" / "ui.lua", store.settings_path()


def make(fake_runner, hypr, paths, syntax_error=None):
    ui_path, settings_path = paths
    runner = fake_runner()
    applier = apply.Applier(hypr, runner=runner, ui_path=ui_path, settings_path=settings_path,
                            launcher=["/bin/hyde-settings"], syntax_check=lambda _text: syntax_error)
    return applier, runner


def pending_with(**input_changes):
    s = store.default_settings()
    s["input"].update(input_changes)
    return s


def test_successful_apply_writes_lua_and_saves(fake_runner, paths):
    hypr = FakeHypr()
    applier, runner = make(fake_runner, hypr, paths)
    saved, pending = store.default_settings(), pending_with(sensitivity=0.5)
    result = applier.apply(saved, pending)
    assert result == apply.Result(True)
    assert paths[0].read_text() == generator.generate(pending)
    assert store.load(paths[1])[0] == pending
    assert hypr.reloads == 1
    assert not any(c[0] == "systemd-run" for c in runner.calls)


def test_every_apply_stops_watchdog_first(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert runner.calls[0] == ["systemctl", "--user", "stop", "hyde-settings-revert.service"]


def test_invalid_settings_write_nothing(fake_runner, paths):
    applier, _ = make(fake_runner, FakeHypr(), paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=5))
    assert not result.ok and "sensibilidade" in result.error
    assert not paths[0].exists()


def test_luac_failure_writes_nothing(fake_runner, paths):
    applier, _ = make(fake_runner, FakeHypr(), paths, syntax_error="ui.lua:1: unexpected symbol")
    result = applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert not result.ok and "unexpected symbol" in result.error
    assert not paths[0].exists()


def test_config_errors_roll_back_and_keep_settings_unsaved(fake_runner, paths):
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("-- previous\n")
    hypr = FakeHypr(errors=["ui.lua:5: bad rule"])
    applier, _ = make(fake_runner, hypr, paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert not result.ok and "bad rule" in result.error
    assert paths[0].read_text() == "-- previous\n"
    assert hypr.reloads == 2  # the failing reload, then the reload of the restored file
    assert not paths[1].exists()


def test_rollback_without_previous_file_restores_empty_config(fake_runner, paths):
    applier, _ = make(fake_runner, FakeHypr(reload_error="no socket"), paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert not result.ok
    assert paths[0].read_text() == generator.HEADER


def test_is_dangerous():
    base = store.default_settings()
    assert not apply.is_dangerous(base, pending_with(sensitivity=0.1))
    assert apply.is_dangerous(base, pending_with(kb_layout="us"))
    other = copy.deepcopy(base)
    other["monitors"] = [{"output": "eDP-1", "mode": "preferred", "position": "auto", "scale": 1.5}]
    assert apply.is_dangerous(base, other)


def test_dangerous_apply_starts_watchdog_and_waits(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    result = applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    assert result == apply.Result(True, awaiting_confirm=True)
    start = next(c for c in runner.calls if c[0] == "systemd-run")
    assert start == ["systemd-run", "--user", "--collect", "--unit=hyde-settings-revert", "/bin/hyde-settings",
                     "--revert-after", "15", str(applier.backup_path), str(paths[0])]
    assert not paths[1].exists()  # saved only on keep()


def test_dangerous_apply_stops_old_watchdog_first(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    stop = runner.calls.index(["systemctl", "--user", "stop", "hyde-settings-revert.service"])
    start = next(i for i, c in enumerate(runner.calls) if c[0] == "systemd-run")
    assert stop < start


def test_watchdog_start_failure_restores_and_fails(fake_runner, paths):
    ui_path, settings_path = paths
    runner = fake_runner()
    runner.responses[("systemd-run", "--user", "--collect", "--unit=hyde-settings-revert", "/bin/hyde-settings",
                      "--revert-after", "15", str(ui_path) + ".bak", str(ui_path))] = (None, "no user bus")
    hypr = FakeHypr()
    applier = apply.Applier(hypr, runner=runner, ui_path=ui_path, settings_path=settings_path,
                            launcher=["/bin/hyde-settings"], syntax_check=lambda _t: None)
    result = applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    assert not result.ok and "no user bus" in result.error
    assert ui_path.read_text() == generator.HEADER
    assert hypr.reloads == 0


def test_keep_stops_watchdog_and_saves(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    pending = pending_with(kb_layout="us")
    applier.apply(store.default_settings(), pending)
    runner.calls.clear()
    applier.keep(pending)
    assert runner.calls == [["systemctl", "--user", "stop", "hyde-settings-revert.service"]]
    assert store.load(paths[1])[0] == pending


def test_revert_restores_backup(fake_runner, paths):
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("-- previous\n")
    applier, _ = make(fake_runner, FakeHypr(), paths)
    applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    assert applier.revert() is None
    assert paths[0].read_text() == "-- previous\n"


def test_revert_after_entry_point(tmp_path):
    backup, target = tmp_path / "ui.lua.bak", tmp_path / "ui.lua"
    backup.write_text("-- old\n")
    target.write_text("-- new\n")
    hypr = FakeHypr()
    slept = []
    assert apply.revert_after(15, backup, target, hypr, sleep=slept.append) == 0
    assert slept == [15]
    assert target.read_text() == "-- old\n"
    assert hypr.reloads == 1
