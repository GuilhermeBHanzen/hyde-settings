"""Thin wrapper over hyprctl. Every call goes through an injectable runner so tests can fake it."""
import json

from hyde_settings import generator, proc


class Hypr:
    def __init__(self, runner=proc.run):
        self.run = runner

    def _json(self, *args):
        out, err = self.run(["hyprctl", *args, "-j"])
        if err is not None:
            return None, err
        try:
            return json.loads(out), None
        except ValueError as exc:
            return None, f"hyprctl {' '.join(args)}: resposta inválida ({exc})"

    def _list(self, name):
        data, _ = self._json(name)
        return data if isinstance(data, list) else []

    def available(self):
        data, err = self._json("version")
        return err is None and isinstance(data, dict)

    def binds(self):
        return self._list("binds")

    def monitors(self):
        return self._list("monitors")

    def clients(self):
        return self._list("clients")

    def option(self, name):
        data, err = self._json("getoption", name)
        if err is not None or not isinstance(data, dict):
            return None
        for key in ("int", "float", "bool"):
            if key in data:
                return data[key]
        if "str" in data:
            return "" if data["str"] == "[[EMPTY]]" else data["str"]
        if "css" in data:
            tokens = str(data["css"]).split()
            try:
                return int(tokens[0]) if tokens else None
            except ValueError:
                return data["css"]
        return None

    def config_errors(self):
        data, err = self._json("configerrors")
        if err is not None:
            return [f"hyprctl configerrors: {err}"]
        if not isinstance(data, list):
            return ["hyprctl configerrors: resposta inválida"]
        return [entry for entry in data if isinstance(entry, str) and entry.strip()]

    def reload(self):
        _, err = self.run(["hyprctl", "reload"])
        return err

    def dispatch(self, lua_expr):
        """hyprctl dispatch takes a Lua expression in the Lua config; it may print 'error: ...' with exit 0."""
        out, err = self.run(["hyprctl", "dispatch", lua_expr])
        if err is not None:
            return err
        text = (out or "").strip()
        return text if text.startswith("error") else None

    def enter_capture(self):
        return self.dispatch(f'hl.dsp.submap("{generator.CAPTURE_SUBMAP}")')

    def leave_capture(self):
        return self.dispatch('hl.dsp.submap("reset")')
