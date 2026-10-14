import copy

import pytest

from hyde_settings import apply, generator, store


class FakeHypr:
    """errors_sequence, when given, is returned call by call; after it runs out, `errors` is returned."""

    def __init__(self, reload_error=None, errors=None, errors_sequence=None):
        self.reload_error = reload_error
        self.errors = list(errors or [])
        self.errors_sequence = [list(e) for e in (errors_sequence or [])]
        self.reloads = 0

    def reload(self):
        self.reloads += 1
        return self.reload_error

    def config_errors(self):
        if self.errors_sequence:
            return self.errors_sequence.pop(0)
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
    applier, runner = make(fake_runner, FakeHypr(), paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=5))
    assert not result.ok and "sensibilidade" in result.error
    assert not paths[0].exists()
    assert runner.calls == []


def test_invalid_apply_leaves_watchdog_alone(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=5))
    assert not result.ok
    assert runner.calls == []


def test_luac_failure_writes_nothing(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths, syntax_error="ui.lua:1: unexpected symbol")
    result = applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert not result.ok and "unexpected symbol" in result.error
    assert not paths[0].exists()
    assert runner.calls == []


def test_backup_is_last_confirmed_settings(fake_runner, paths):
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("-- unconfirmed dangerous state\n")
    applier, _ = make(fake_runner, FakeHypr(), paths)
    saved = store.default_settings()
    applier.apply(saved, pending_with(kb_layout="us"))
    assert applier.backup_path.read_text() == generator.generate(saved)


def test_config_errors_roll_back_and_keep_settings_unsaved(fake_runner, paths):
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("-- previous\n")
    hypr = FakeHypr(errors_sequence=[[], ["ui.lua:5: bad rule"]])  # clean baseline, then the new error
    applier, _ = make(fake_runner, hypr, paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert not result.ok and "bad rule" in result.error
    assert paths[0].read_text() == generator.generate(store.default_settings())
    assert hypr.reloads == 2  # the failing reload, then the reload of the restored file
    assert not paths[1].exists()


def test_preexisting_config_error_does_not_block_apply(fake_runner, paths):
    hypr = FakeHypr(errors_sequence=[["legacy.lua:1: old"], ["legacy.lua:1: old"]])
    applier, _ = make(fake_runner, hypr, paths)
    pending = pending_with(sensitivity=0.5)
    assert applier.apply(store.default_settings(), pending) == apply.Result(True)
    assert store.load(paths[1])[0] == pending


def test_rollback_without_previous_file_restores_last_confirmed(fake_runner, paths):
    applier, _ = make(fake_runner, FakeHypr(reload_error="no socket"), paths)
    result = applier.apply(store.default_settings(), pending_with(sensitivity=0.5))
    assert not result.ok
    assert paths[0].read_text() == generator.generate(store.default_settings())


def test_is_dangerous():
    base = store.default_settings()
    assert not apply.is_dangerous(base, pending_with(sensitivity=0.1))
    assert apply.is_dangerous(base, pending_with(kb_layout="us"))
    other = copy.deepcopy(base)
    other["monitors"] = [{"output": "eDP-1", "mode": "preferred", "position": "auto", "scale": 1.5}]
    assert apply.is_dangerous(base, other)


def _dangerous_pair():
    saved = store.default_settings()
    saved["monitors"] = [{"output": "eDP-1", "mode": "preferred", "position": "auto", "scale": 1.0}]
    saved["input"].update(kb_layout="br", kb_variant="abnt2")
    pending = copy.deepcopy(saved)
    pending["monitors"] = [{"output": "eDP-1", "mode": "preferred", "position": "auto", "scale": 1.25}]
    pending["input"].update(kb_layout="us", kb_variant="intl", sensitivity=0.5)
    return saved, pending


def test_discard_dangerous_takes_dangerous_fields_from_saved():
    saved, pending = _dangerous_pair()
    result = apply.discard_dangerous(saved, pending)
    assert result["monitors"] == saved["monitors"]
    assert result["input"]["kb_layout"] == "br"
    assert result["input"]["kb_variant"] == "abnt2"


def test_discard_dangerous_keeps_non_dangerous_pending_fields():
    saved, pending = _dangerous_pair()
    result = apply.discard_dangerous(saved, pending)
    assert result["input"]["sensitivity"] == 0.5


def test_discard_dangerous_does_not_mutate_inputs():
    saved, pending = _dangerous_pair()
    saved_before, pending_before = copy.deepcopy(saved), copy.deepcopy(pending)
    result = apply.discard_dangerous(saved, pending)
    assert saved == saved_before
    assert pending == pending_before
    assert result["monitors"] is not saved["monitors"]
    assert result["input"] is not pending["input"]


def test_discard_dangerous_result_is_not_dangerous():
    saved, pending = _dangerous_pair()
    assert apply.is_dangerous(saved, pending)
    assert not apply.is_dangerous(saved, apply.discard_dangerous(saved, pending))


def test_dangerous_apply_starts_watchdog_and_waits(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    result = applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    assert result == apply.Result(True, awaiting_confirm=True)
    start = next(c for c in runner.calls if c[0] == "systemd-run")
    assert start == ["systemd-run", "--user", "--collect", "--service-type=exec", "--unit=hyde-settings-revert",
                     "/bin/hyde-settings", "--revert-after", "20", str(applier.backup_path), str(paths[0])]
    assert not paths[1].exists()  # saved only on keep()


def test_dangerous_apply_stops_old_watchdog_first(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    stop = runner.calls.index(["systemctl", "--user", "stop", "hyde-settings-revert.service"])
    start = next(i for i, c in enumerate(runner.calls) if c[0] == "systemd-run")
    assert stop < start


def test_watchdog_start_failure_restores_and_fails(fake_runner, paths):
    ui_path, settings_path = paths
    ui_path.parent.mkdir(parents=True)
    ui_path.write_text("-- previous\n")
    runner = fake_runner()
    runner.responses[("systemd-run", "--user", "--collect", "--service-type=exec", "--unit=hyde-settings-revert",
                      "/bin/hyde-settings", "--revert-after", "20", str(ui_path) + ".bak", str(ui_path))] = (None, "no user bus")
    hypr = FakeHypr()
    applier = apply.Applier(hypr, runner=runner, ui_path=ui_path, settings_path=settings_path,
                            launcher=["/bin/hyde-settings"], syntax_check=lambda _t: None)
    result = applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    assert not result.ok and "no user bus" in result.error
    assert ui_path.read_text() == "-- previous\n"  # ui.lua is never written when the watchdog cannot start
    assert hypr.reloads == 0


def test_keep_stops_watchdog_and_saves(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    pending = pending_with(kb_layout="us")
    applier.apply(store.default_settings(), pending)
    runner.calls.clear()
    runner.responses[("systemctl", "--user", "is-active", "hyde-settings-revert.service")] = ("active\n", None)
    assert applier.keep(pending) is None
    assert runner.calls == [
        ["systemctl", "--user", "is-active", "hyde-settings-revert.service"],
        ["systemctl", "--user", "stop", "hyde-settings-revert.service"],
    ]
    assert store.load(paths[1])[0] == pending


def test_keep_after_watchdog_fired_does_not_save(fake_runner, paths):
    applier, runner = make(fake_runner, FakeHypr(), paths)
    pending = pending_with(kb_layout="us")
    applier.apply(store.default_settings(), pending)
    runner.responses[("systemctl", "--user", "is-active", "hyde-settings-revert.service")] = (None, "inactive")
    err = applier.keep(pending)
    assert err == "A reversão automática já aconteceu; aplique de novo."
    assert not paths[1].exists()


def test_revert_restores_backup(fake_runner, paths):
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("-- previous\n")
    applier, _ = make(fake_runner, FakeHypr(), paths)
    applier.apply(store.default_settings(), pending_with(kb_layout="us"))
    assert applier.revert() is None
    assert paths[0].read_text() == generator.generate(store.default_settings())


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
