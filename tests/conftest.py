import pytest


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    """Redirect every store.config_dir() path into a temp dir."""
    home = tmp_path / "config"
    home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    return home


class FakeRunner:
    """Stands in for proc.run: maps a command tuple to (stdout, error) and records every call.

    Unknown commands succeed with empty output, so tests only list what they care about.
    """

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def __call__(self, cmd, timeout=10):
        self.calls.append(list(cmd))
        return self.responses.get(tuple(cmd), ("", None))


@pytest.fixture
def fake_runner():
    return FakeRunner
