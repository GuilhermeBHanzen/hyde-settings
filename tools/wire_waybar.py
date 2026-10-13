"""Add the custom/hyde-settings module next to custom/vaio-center in the user's waybar layout."""
import re
import sys
from pathlib import Path

MODULE = '"custom/hyde-settings"'
_ANCHOR = re.compile(r'^(?P<indent>\s*)"custom/vaio-center",\n', re.MULTILINE)


def wire(text):
    """Return the edited layout text, or None when already wired or no anchor was found."""
    if MODULE in text:
        return None
    match = _ANCHOR.search(text)
    if match is None:
        return None
    insert = f'{match.group("indent")}{MODULE},\n'
    return text[: match.end()] + insert + text[match.end():]


def main(argv):
    path = Path(argv[1])
    text = path.read_text()
    wired = wire(text)
    if wired is None:
        if MODULE not in text:
            print(f"wire_waybar: no custom/vaio-center anchor in {path}; add {MODULE} by hand", file=sys.stderr)
        return 0
    path.write_text(wired)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
