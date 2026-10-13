"""Shared vocabulary: modifier keys, key combos, curated dispatchers and app roles."""

MODS = ("SUPER", "CTRL", "ALT", "SHIFT")
MOD_BITS = {"SHIFT": 1, "CTRL": 4, "ALT": 8, "SUPER": 64}
_MOD_ALIASES = {"CONTROL": "CTRL", "MOD4": "SUPER", "WIN": "SUPER", "LOGO": "SUPER"}


def normalize_key(key):
    """Single characters are upper-cased; named keys (Delete, Tab, mouse:272) are kept as written."""
    return key.upper() if len(key) == 1 else key


def parse_combo(text):
    """'shift + super + m' -> (('SUPER', 'SHIFT'), 'M'). Raises ValueError when malformed."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("combinação vazia")
    parts = [part.strip() for part in text.split("+")]
    *mod_parts, key = parts
    if not key:
        raise ValueError(f"combinação sem tecla: {text!r}")
    if " " in key:
        raise ValueError(f"tecla inválida {key!r} em {text!r}")
    mods = set()
    for part in mod_parts:
        name = _MOD_ALIASES.get(part.upper(), part.upper())
        if name not in MODS:
            raise ValueError(f"modificador desconhecido {part!r} em {text!r}")
        if name in mods:
            raise ValueError(f"modificador repetido em {text!r}")
        mods.add(name)
    return tuple(mod for mod in MODS if mod in mods), normalize_key(key)


def format_combo(mods, key):
    return " + ".join([*mods, key])


def normalize_combo(text):
    return format_combo(*parse_combo(text))


def combo_id(text):
    """Identity used to compare combos: (modifier bitmask, lower-cased key)."""
    mods, key = parse_combo(text)
    return sum(MOD_BITS[mod] for mod in mods), key.lower()


def mods_from_mask(mask):
    return tuple(mod for mod in MODS if mask & MOD_BITS[mod])


def mode_matches(a, b):
    """'1920x1080@144' matches '1920x1080@144.00' (same resolution, rate within 0.5 Hz)."""
    try:
        res_a, rate_a = a.split("@")
        res_b, rate_b = b.split("@")
        return res_a == res_b and abs(float(rate_a) - float(rate_b)) < 0.5
    except ValueError:
        return a == b


# name -> whether the action takes a workspace number (args: {"n": int})
DISPATCHERS = {
    "close": False,
    "kill": False,
    "maximize": False,
    "fullscreen": False,
    "float": False,
    "cycle_next": False,
    "workspace": True,
    "move_to_workspace": True,
}

DISPATCH_LABELS = {
    "close": "Fechar janela",
    "kill": "Matar janela",
    "maximize": "Maximizar (alternar)",
    "fullscreen": "Tela cheia (alternar)",
    "float": "Flutuar (alternar)",
    "cycle_next": "Alternar foco",
    "workspace": "Ir para o workspace N",
    "move_to_workspace": "Mover janela para o workspace N",
}

ROLES = ("editor", "browser", "terminal", "explorer")
ROLE_KEYS = {"editor": "SUPER + C", "browser": "SUPER + B", "terminal": "SUPER + T", "explorer": "SUPER + E"}
ROLE_DESCRIPTIONS = {
    "editor": "[Launcher|Apps] text editor",
    "browser": "[Launcher|Apps] web browser",
    "terminal": "[Launcher|Apps] terminal emulator",
    "explorer": "[Launcher|Apps] file explorer",
}
