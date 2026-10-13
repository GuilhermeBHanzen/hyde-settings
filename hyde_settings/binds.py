"""Pure keybind logic: merge live binds with settings, tag origins, group, detect conflicts, capture."""
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from hyde_settings import model

MODIFIER_KEYS = frozenset({
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L", "Super_R",
    "Meta_L", "Meta_R", "Hyper_L", "Hyper_R", "ISO_Level3_Shift", "Caps_Lock", "Num_Lock",
})
_BIND_RE = re.compile(r'hl\.bind\(\s*"([^"]+)"')
_CATEGORY_RE = re.compile(r"^\[([^\]|]+)")


@dataclass(frozen=True)
class Row:
    combo: str
    label: str
    category: str
    origin: str  # "hyde" | "yours" | "manual" | "removed"
    bind_index: int | None = None  # index into settings["binds"]
    role: str | None = None  # app role when the bind comes from settings["apps"]


def live_combo(bind):
    return model.format_combo(model.mods_from_mask(bind.get("modmask", 0)), model.normalize_key(bind.get("key", "")))


def category(description):
    match = _CATEGORY_RE.match(description or "")
    return match.group(1).strip() if match else "Outros"


def label(description):
    text = re.sub(r"^\[[^\]]*\]\s*", "", description or "").strip()
    return text or "(sem descrição)"


def action_summary(action):
    kind = action.get("type")
    if kind == "exec":
        return action.get("command", "")
    if kind == "dispatch":
        text = model.DISPATCH_LABELS.get(action.get("name"), action.get("name", ""))
        if model.DISPATCHERS.get(action.get("name")):
            text += f" ({(action.get('args') or {}).get('n')})"
        return text
    return "(removido)"


def scan_manual(paths):
    """Combo ids bound with a literal hl.bind("...") in hand-written files. Reads text only."""
    ids = set()
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.lstrip().startswith("--"):
                continue
            for match in _BIND_RE.finditer(line):
                try:
                    ids.add(model.combo_id(match.group(1)))
                except ValueError:
                    pass
    return ids


def manual_files(hypr_dir):
    return sorted(p for p in Path(hypr_dir).glob("*.lua") if p.name != "ui.lua")


def build_rows(live, settings, manual_ids):
    rows, taken = [], set()
    for role in model.ROLES:
        entry = settings["apps"].get(role) or {}
        if entry.get("command"):
            combo = model.normalize_combo(entry["key"])
            desc = model.ROLE_DESCRIPTIONS[role]
            rows.append(Row(combo, f"{label(desc)}: {entry['command']}", category(desc), "yours", role=role))
            taken.add(model.combo_id(combo))
    for index, bind in enumerate(settings["binds"]):
        combo = model.normalize_combo(bind["key"])
        if bind["action"]["type"] == "unbind":
            rows.append(Row(combo, "(removido)", "Removidos", "removed", bind_index=index))
        else:
            desc = bind.get("description") or ""
            text = label(desc) if desc else action_summary(bind["action"])
            rows.append(Row(combo, text, category(desc), "yours", bind_index=index))
        taken.add(model.combo_id(combo))
    for bind in live:
        if bind.get("submap") or not bind.get("key"):
            continue
        combo = live_combo(bind)
        cid = model.combo_id(combo)
        if cid in taken:
            continue
        desc = bind.get("description", "")
        rows.append(Row(combo, label(desc), category(desc), "manual" if cid in manual_ids else "hyde"))
    return sorted(rows, key=lambda r: (r.category.lower(), r.combo.lower()))


def conflicts(combo, rows, editing=None):
    """Active rows already using combo, ignoring removed rows and the row being edited."""
    cid = model.combo_id(combo)
    return [
        row for row in rows
        if row.origin != "removed" and row != editing and model.combo_id(row.combo) == cid
    ]


def combo_from_gtk(keyval_name, mods):
    """keyval_name: Gdk.keyval_name of the unshifted key; mods: model.MODS names held.

    Bare modifier presses return None so capture keeps waiting for the real key.
    Bare Escape is the caller's cancel key and must be handled before calling;
    this function does not special-case it, so SUPER + Escape stays capturable.
    """
    if not keyval_name or keyval_name in MODIFIER_KEYS:
        return None
    return model.format_combo(tuple(mod for mod in model.MODS if mod in mods), model.normalize_key(keyval_name))


def command_missing(command, which=shutil.which):
    """True when the command's program is not on PATH (or the command cannot be parsed)."""
    try:
        words = shlex.split(command)
    except ValueError:
        return True
    return not words or which(words[0]) is None
