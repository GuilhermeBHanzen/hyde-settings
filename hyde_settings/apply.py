"""Apply transaction: validate, generate, syntax-check, write ui.lua, reload, roll back on error.

Dangerous changes (monitors, keyboard layout) start a detached watchdog that restores the
previous ui.lua after REVERT_SECONDS unless the user confirms; it survives the app dying.
"""
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from hyde_settings import generator, proc, store

WATCHDOG_UNIT = "hyde-settings-revert"
REVERT_SECONDS = 15
WATCHDOG_GRACE = 5  # the UI countdown (REVERT_SECONDS) always decides first; the watchdog is a backstop


def ui_lua_path():
    return store.config_dir() / "hypr" / "ui.lua"


def check_syntax(text, runner=proc.run):
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as handle:
        handle.write(text)
        path = handle.name
    try:
        _, err = runner(["luac", "-p", path])
    finally:
        Path(path).unlink(missing_ok=True)
    return err


def is_dangerous(saved, pending):
    return (
        saved["monitors"] != pending["monitors"]
        or saved["input"].get("kb_layout") != pending["input"].get("kb_layout")
        or saved["input"].get("kb_variant") != pending["input"].get("kb_variant")
    )


@dataclass
class Result:
    ok: bool
    error: str | None = None
    awaiting_confirm: bool = False


class Applier:
    def __init__(self, hypr, runner=proc.run, ui_path=None, settings_path=None, launcher=None, syntax_check=None):
        self.hypr = hypr
        self.run = runner
        self.ui_path = Path(ui_path) if ui_path else ui_lua_path()
        self.settings_path = settings_path
        self.launcher = launcher or [str(Path.home() / ".local" / "bin" / "hyde-settings")]
        self.syntax_check = syntax_check or (lambda text: check_syntax(text, runner))

    @property
    def backup_path(self):
        return self.ui_path.with_name(self.ui_path.name + ".bak")

    def apply(self, saved, pending):
        errors = store.validate(pending)
        if errors:
            return Result(False, "\n".join(errors))
        text = generator.generate(pending)
        err = self.syntax_check(text)
        if err:
            return Result(False, f"Lua gerado inválido: {err}")
        self.stop_watchdog()
        self._backup(saved)
        store.write_atomic(self.ui_path, text)
        dangerous = is_dangerous(saved, pending)
        if dangerous:
            err = self._start_watchdog()
            if err:
                self._restore()
                return Result(False, f"não foi possível iniciar a reversão automática: {err}")
        failure = self.hypr.reload()
        errors = [] if failure else self.hypr.config_errors()
        if failure or errors:
            if dangerous:
                self.stop_watchdog()
            self._restore()
            self.hypr.reload()
            return Result(False, failure or "\n".join(errors))
        if dangerous:
            return Result(True, awaiting_confirm=True)
        store.save(pending, self.settings_path)
        return Result(True)

    def keep(self, pending):
        """Confirm a dangerous apply. Refuses to save if the watchdog already reverted ui.lua."""
        out, err = self.run(["systemctl", "--user", "is-active", f"{WATCHDOG_UNIT}.service"])
        if err or (out or "").strip() != "active":
            return "A reversão automática já aconteceu; aplique de novo."
        self.stop_watchdog()
        store.save(pending, self.settings_path)
        return None

    def revert(self):
        self.stop_watchdog()
        self._restore()
        return self.hypr.reload()

    def stop_watchdog(self):
        self.run(["systemctl", "--user", "stop", f"{WATCHDOG_UNIT}.service"])

    def _start_watchdog(self):
        self.stop_watchdog()
        _, err = self.run([
            "systemd-run", "--user", "--collect", f"--unit={WATCHDOG_UNIT}", *self.launcher,
            "--revert-after", str(REVERT_SECONDS + WATCHDOG_GRACE), str(self.backup_path), str(self.ui_path),
        ])
        return err

    def _backup(self, saved):
        """Backup is always the last confirmed settings, never the current (maybe unconfirmed) ui.lua."""
        store.write_atomic(self.backup_path, generator.generate(saved))

    def _restore(self):
        store.write_atomic(self.ui_path, self.backup_path.read_text())


def revert_after(seconds, backup, target, hypr, sleep=time.sleep):
    """Watchdog body: wait, put the backup back, reload. Runs in its own systemd unit."""
    sleep(seconds)
    store.write_atomic(Path(target), Path(backup).read_text())
    hypr.reload()
    return 0
