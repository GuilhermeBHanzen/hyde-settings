import pytest

from hyde_settings import model


def test_parse_combo_orders_mods_and_uppercases_single_char_keys():
    assert model.parse_combo("shift + super + m") == (("SUPER", "SHIFT"), "M")


def test_parse_combo_accepts_aliases_and_named_keys():
    assert model.parse_combo("CONTROL + ALT + Delete") == (("CTRL", "ALT"), "Delete")
    assert model.parse_combo("F10") == ((), "F10")


@pytest.mark.parametrize("bad", ["", "SUPER +", "HYPER + K", "SUPER + SUPER + K", "SUPER + two words"])
def test_parse_combo_rejects_malformed(bad):
    with pytest.raises(ValueError):
        model.parse_combo(bad)


def test_normalize_combo_round_trips():
    assert model.normalize_combo("alt+tab") == "ALT + tab"
    assert model.normalize_combo("SUPER + c") == "SUPER + C"


def test_combo_id_is_case_insensitive_on_key():
    assert model.combo_id("ALT + TAB") == model.combo_id("alt + Tab") == (8, "tab")


def test_mods_from_mask():
    assert model.mods_from_mask(64 | 1) == ("SUPER", "SHIFT")
    assert model.mods_from_mask(0) == ()


def test_mode_matches_ignores_rate_formatting():
    assert model.mode_matches("1920x1080@144", "1920x1080@144.00")
    assert not model.mode_matches("1920x1080@144", "1920x1080@60.02")
    assert not model.mode_matches("1920x1080@144", "2560x1440@144")


def test_every_dispatcher_has_a_label():
    assert set(model.DISPATCH_LABELS) == set(model.DISPATCHERS)
