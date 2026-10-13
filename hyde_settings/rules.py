"""Pure helpers for the window-rules page."""
import re

_MATCH_LABELS = (("class", "classe"), ("title", "título"), ("initial_title", "título inicial"))


def class_regex(window_class):
    return f"^({re.escape(window_class)})$"


def unique_name(base, taken):
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "regra"
    name, n = slug, 2
    while name in taken:
        name = f"{slug}-{n}"
        n += 1
    return name


def summary(rule):
    parts = [f"{label} {rule['match'][key]}" for key, label in _MATCH_LABELS if rule["match"].get(key)]
    if rule.get("opacity"):
        parts.append("opacidade " + "/".join(f"{x:g}" for x in rule["opacity"]))
    if rule.get("float") is True:
        parts.append("flutua")
    elif rule.get("float") is False:
        parts.append("não flutua")
    if rule.get("idle_inhibit") == "always":
        parts.append("não suspende")
    elif rule.get("idle_inhibit") == "fullscreen":
        parts.append("não suspende em tela cheia")
    return " · ".join(parts)
