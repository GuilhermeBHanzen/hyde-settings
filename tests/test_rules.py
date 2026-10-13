from hyde_settings import rules


def test_class_regex_escapes():
    assert rules.class_regex("kitty") == "^(kitty)$"
    assert rules.class_regex("org.kde.dolphin") == "^(org\\.kde\\.dolphin)$"


def test_unique_name():
    assert rules.unique_name("Brave Browser!", set()) == "brave-browser"
    assert rules.unique_name("kitty", {"kitty", "kitty-2"}) == "kitty-3"
    assert rules.unique_name("!!!", set()) == "regra"


def test_summary():
    rule = {"name": "k", "match": {"class": "^(kitty)$"}, "opacity": [0.9, 0.8], "float": True,
            "idle_inhibit": "fullscreen"}
    assert rules.summary(rule) == "classe ^(kitty)$ · opacidade 0.9/0.8 · flutua · não suspende em tela cheia"
    assert rules.summary({"name": "t", "match": {"title": "x"}, "float": False}) == "título x · não flutua"


def test_summary_initial_title_and_idle_always():
    rule = {"name": "s", "match": {"initial_title": "Spotify"}, "idle_inhibit": "always"}
    assert rules.summary(rule) == "título inicial Spotify · não suspende"
