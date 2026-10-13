import pytest


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    """Redirect every store.config_dir() path into a temp dir."""
    home = tmp_path / "config"
    home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    return home
