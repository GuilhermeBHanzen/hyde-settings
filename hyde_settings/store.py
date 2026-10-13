"""Load, validate and atomically save ~/.config/hyde-settings/settings.json."""
import contextlib
import copy
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from hyde_settings import model

VERSION = 1
_MODE_RE = re.compile(r"^\d+x\d+@\d+(\.\d+)?$")
_POS_RE = re.compile(r"^-?\d+x-?\d+$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MATCH_KEYS = ("class", "title", "initial_title")


class SettingsError(ValueError):
    pass


def config_dir():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def settings_path():
    return config_dir() / "hyde-settings" / "settings.json"


def default_settings():
    return {
        "version": VERSION,
        "monitors": [],
        "input": {"kb_layout": None, "kb_variant": None, "sensitivity": None,
                  "numlock_by_default": None, "natural_scroll": None},
        "appearance": {"active_opacity": None, "inactive_opacity": None, "gaps_in": None,
                       "gaps_out": None, "border_size": None, "rounding": None,
                       "blur": {"enabled": None, "size": None, "passes": None}},
        "apps": {role: {"command": None, "key": model.ROLE_KEYS[role]} for role in model.ROLES},
        "binds": [],
        "window_rules": [],
        "layer_rules": [],
    }


def merge_defaults(data):
    """Fill keys missing from an older or hand-edited file with defaults; keep unknown keys."""
    def merge(default, value):
        if isinstance(default, dict) and isinstance(value, dict):
            out = {k: merge(v, value[k]) if k in value else copy.deepcopy(v) for k, v in default.items()}
            out.update({k: v for k, v in value.items() if k not in out})
            return out
        return value
    return merge(default_settings(), data)


def _is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _obj(errors, label, value):
    """Optional nested object: None counts as absent, any other non-object is reported."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label}: esperado objeto")
        return {}
    return value


def _section(errors, name, value):
    """Top-level object section: a hand-edited null or non-object is reported, never used."""
    if not isinstance(value, dict):
        errors.append(f"{name}: esperado objeto")
        return {}
    return value


def _items(errors, name, value, item_label):
    """Top-level list section: returns (number, dict) for object items and reports the rest."""
    if not isinstance(value, list):
        errors.append(f"{name}: esperado lista")
        return []
    items = []
    for i, item in enumerate(value):
        if isinstance(item, dict):
            items.append((i + 1, item))
        else:
            errors.append(f"{item_label} {i + 1}: esperado objeto")
    return items


def _check_range(errors, label, value, lo, hi, integer=False):
    if value is None:
        return
    if not _is_num(value) or (integer and not isinstance(value, int)) or not lo <= value <= hi:
        errors.append(f"{label}: valor inválido {value!r} (esperado {lo}–{hi})")


def _check_bool(errors, label, value):
    if value is not None and not isinstance(value, bool):
        errors.append(f"{label}: esperado verdadeiro ou falso")


def _check_combo(errors, label, text):
    try:
        return model.normalize_combo(text)
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
        return None


def _check_regex(errors, label, value):
    if not isinstance(value, str):
        errors.append(f"{label}: esperado texto")
        return
    try:
        re.compile(value)
    except re.error as exc:
        errors.append(f"{label}: regex inválida ({exc})")


def window_rule_errors(rule, taken_names):
    """Errors for one window rule; taken_names are the names of the other rules."""
    errors = []
    name = rule.get("name")
    label = f"regra {name or '(sem nome)'}"
    if not isinstance(name, str) or not _NAME_RE.match(name):
        errors.append(f"{label}: nome inválido (use letras, números, - e _)")
    elif name in taken_names:
        errors.append(f"{label}: nome repetido")
    match = _obj(errors, f"{label}: match", rule.get("match"))
    fields = {k: match.get(k) for k in _MATCH_KEYS if match.get(k)}
    if not fields:
        errors.append(f"{label}: informe classe, título ou título inicial")
    for key, value in fields.items():
        _check_regex(errors, f"{label}: {key}", value)
    opacity = rule.get("opacity")
    if opacity is not None and (
        not isinstance(opacity, list) or len(opacity) not in (2, 3)
        or not all(_is_num(x) and 0 <= x <= 1 for x in opacity)
    ):
        errors.append(f"{label}: opacidade inválida {opacity!r}")
    _check_bool(errors, f"{label}: flutuar", rule.get("float"))
    if rule.get("idle_inhibit") not in (None, "always", "fullscreen"):
        errors.append(f"{label}: não suspender inválido {rule.get('idle_inhibit')!r}")
    if opacity is None and rule.get("float") is None and rule.get("idle_inhibit") is None:
        errors.append(f"{label}: nenhum efeito definido")
    return errors


def validate(settings):
    if settings.get("version") != VERSION:
        return [f"versão de configuração desconhecida: {settings.get('version')!r}"]
    errors = []
    for number, mon in _items(errors, "monitores", settings.get("monitors"), "monitor"):
        label = f"monitor {number}"
        if not isinstance(mon.get("output"), str) or not mon["output"]:
            errors.append(f"{label}: saída vazia")
        mode = mon.get("mode")
        if not (mode == "preferred" or (isinstance(mode, str) and _MODE_RE.match(mode))):
            errors.append(f"{label}: modo inválido {mode!r}")
        pos = mon.get("position")
        if not (pos == "auto" or (isinstance(pos, str) and _POS_RE.match(pos))):
            errors.append(f"{label}: posição inválida {pos!r}")
        scale = mon.get("scale")
        if not _is_num(scale) or not 0.25 <= scale <= 4:
            errors.append(f"{label}: escala inválida {scale!r} (esperado 0.25–4)")
    inp = _section(errors, "entrada", settings.get("input"))
    for key in ("kb_layout", "kb_variant"):
        value = inp.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip() or " " in value):
            errors.append(f"entrada.{key}: valor inválido {value!r}")
    _check_range(errors, "entrada.sensibilidade", inp.get("sensitivity"), -1.0, 1.0)
    _check_bool(errors, "entrada.numlock", inp.get("numlock_by_default"))
    _check_bool(errors, "entrada.scroll natural", inp.get("natural_scroll"))
    app = _section(errors, "aparência", settings.get("appearance"))
    _check_range(errors, "aparência.opacidade ativa", app.get("active_opacity"), 0.0, 1.0)
    _check_range(errors, "aparência.opacidade inativa", app.get("inactive_opacity"), 0.0, 1.0)
    _check_range(errors, "aparência.espaço entre janelas", app.get("gaps_in"), 0, 100, integer=True)
    _check_range(errors, "aparência.margem", app.get("gaps_out"), 0, 200, integer=True)
    _check_range(errors, "aparência.borda", app.get("border_size"), 0, 20, integer=True)
    _check_range(errors, "aparência.arredondamento", app.get("rounding"), 0, 50, integer=True)
    blur = _obj(errors, "aparência.blur", app.get("blur"))
    _check_bool(errors, "aparência.blur", blur.get("enabled"))
    _check_range(errors, "aparência.blur tamanho", blur.get("size"), 1, 50, integer=True)
    _check_range(errors, "aparência.blur passes", blur.get("passes"), 1, 10, integer=True)

    used = {}

    def claim(combo, owner):
        if combo is None:
            return
        cid = model.combo_id(combo)
        if cid in used:
            errors.append(f"atalho {combo} usado duas vezes ({used[cid]} e {owner})")
        else:
            used[cid] = owner

    apps = _section(errors, "apps", settings.get("apps"))
    for role in model.ROLES:
        entry = _obj(errors, f"apps.{role}", apps.get(role))
        command = entry.get("command")
        if command is not None and (not isinstance(command, str) or not command.strip()):
            errors.append(f"apps.{role}: comando vazio")
        combo = _check_combo(errors, f"apps.{role}", entry.get("key"))
        if command:
            claim(combo, f"app {role}")
    for number, bind in _items(errors, "atalhos", settings.get("binds"), "atalho"):
        label = f"atalho {number}"
        combo = _check_combo(errors, label, bind.get("key"))
        action = _obj(errors, f"{label}: ação", bind.get("action"))
        kind = action.get("type")
        if kind == "exec":
            if not isinstance(action.get("command"), str) or not action["command"].strip():
                errors.append(f"{label}: comando vazio")
        elif kind == "dispatch":
            name = action.get("name")
            if not isinstance(name, str) or name not in model.DISPATCHERS:
                errors.append(f"{label}: ação desconhecida {name!r}")
            elif model.DISPATCHERS[name]:
                args = _obj(errors, f"{label}: argumentos", action.get("args"))
                n = args.get("n")
                if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 99:
                    errors.append(f"{label}: número de workspace inválido {n!r}")
        elif kind != "unbind":
            errors.append(f"{label}: tipo de ação desconhecido {kind!r}")
        if bind.get("description") is not None and not isinstance(bind["description"], str):
            errors.append(f"{label}: descrição inválida")
        claim(combo, label)
    names = set()
    for _, rule in _items(errors, "regras de janela", settings.get("window_rules"), "regra de janela"):
        errors.extend(window_rule_errors(rule, names))
        if isinstance(rule.get("name"), str):
            names.add(rule["name"])
    layer_names = set()
    for _, rule in _items(errors, "regras de camada", settings.get("layer_rules"), "regra de camada"):
        name = rule.get("name")
        label = f"regra de camada {name or '(sem nome)'}"
        if not isinstance(name, str) or not _NAME_RE.match(name) or name in layer_names:
            errors.append(f"{label}: nome inválido ou repetido")
        if isinstance(name, str):
            layer_names.add(name)
        match = _obj(errors, f"{label}: match", rule.get("match"))
        _check_regex(errors, f"{label}: namespace", match.get("namespace"))
        _check_bool(errors, f"{label}: blur", rule.get("blur"))
        _check_range(errors, f"{label}: ignore_alpha", rule.get("ignore_alpha"), 0, 1)
    return errors


def load(path=None):
    """Return (settings, error). A non-None error means the caller must stay read-only."""
    path = Path(path) if path else settings_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default_settings(), None
    except UnicodeDecodeError as exc:
        return default_settings(), f"{path}: UTF-8 inválido ({exc})"
    except OSError as exc:
        return default_settings(), f"{path}: {exc}"
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        return default_settings(), f"{path}: JSON inválido ({exc})"
    if not isinstance(data, dict):
        return default_settings(), f"{path}: formato inválido"
    if data.get("version") != VERSION:
        return default_settings(), f"{path}: versão desconhecida {data.get('version')!r}"
    settings = merge_defaults(data)
    errors = validate(settings)
    if errors:
        return settings, f"{path}: " + "; ".join(errors)
    return settings, None


def write_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def save(settings, path=None):
    errors = validate(settings)
    if errors:
        raise SettingsError("; ".join(errors))
    path = Path(path) if path else settings_path()
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    write_atomic(path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def count_changes(a, b):
    """Number of differing leaves between two settings trees (list length changes count once each)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return sum(count_changes(a.get(k), b.get(k)) for k in a.keys() | b.keys())
    if isinstance(a, list) and isinstance(b, list):
        return sum(count_changes(x, y) for x, y in zip(a, b)) + abs(len(a) - len(b))
    return 0 if a == b else 1
