# hyde-settings

A GTK4/libadwaita settings app for [HyDE](https://github.com/HyDE-Project/HyDE) on Hyprland's Lua config. It edits keybinds, default apps, monitor and input, window rules and appearance, and your changes survive HyDE updates.

> The UI is in Brazilian Portuguese (pt-BR).

## Why

HyDE overwrites its own config files on every update. In October 2026 a single update migrated hyprlang `.conf` files to Lua and silently dropped monitor scale, keyboard layout, custom keybinds and waybar modules.

hyde-settings never edits HyDE's files and never parses your hand-written Lua. It keeps your settings in its own JSON file and generates one Lua file that Hyprland loads **last**:

```
~/.config/hyde-settings/settings.json ──► generator ──► ~/.config/hypr/ui.lua ──► hyprctl reload
            (single source of truth)                    (generated, loaded last)
```

Hand-written files under `~/.config/hypr/` keep working. Settings made in the app win on conflicts, because `ui.lua` loads after them.

## Features

| Page | What it does |
|---|---|
| **Atalhos** (keybinds) | Lists every live bind (from `hyprctl binds -j`), grouped and tagged by origin: HyDE, yours, or hand-written. You can add, replace or remove binds, with key capture: Hyprland's binds are paused through a submap while you press the combo. Conflicts are flagged. |
| **Apps padrão** (default apps) | Sets the launcher commands for `SUPER+C/B/T/E`, plus "open files with" MIME defaults through `xdg-mime`, with undo. |
| **Monitor e entrada** | Sets resolution/refresh rate, scale and position per monitor, plus keyboard layout/variant, sensitivity, natural scroll and numlock. |
| **Regras de janela** | Sets per-app opacity, float and idle-inhibit, with a picker that grabs the class from an open window. |
| **Aparência** | Sets global opacity, gaps, border, rounding and blur. Each control shows the live value and has a "reset to HyDE" button. |

## Safety

- **Validation:** every change is validated before anything is written, and the generated Lua is syntax-checked with `luac -p`.
- **Atomic apply with rollback:** `ui.lua` is written atomically and Hyprland is reloaded. If the reload reports new config errors, the app restores the last confirmed config and reloads again.
- **15-second revert for dangerous changes:** a scale, resolution or keyboard-layout change asks "Keep these settings?". A detached `systemd-run --user` watchdog reverts automatically if you don't confirm, even if the app crashes or the screen becomes unreadable.
- **Escape hatch during key capture:** pressing `Escape` always leaves the capture submap.

## Requirements

- Hyprland ≥ 0.56 with the Lua config (HyDE's `~/.local/share/hypr/hyde.lua` entry point)
- Python ≥ 3.12, PyGObject with GTK 4 and libadwaita ≥ 1.5
- `luac` (Lua 5.5), `xdg-utils`, a systemd user session

## Install

```sh
git clone https://github.com/gladiusdei/hyde-settings
cd hyde-settings
./install.sh
```

The installer runs at user level and needs no root. It installs:

- the app into `~/.local/lib/hyde-settings`;
- a launcher at `~/.local/bin/hyde-settings`;
- a desktop entry;
- an optional waybar module (`custom/hyde-settings`).

On first launch, a banner offers to append `require("ui")` to the end of `~/.config/hypr/hyprland.lua`. This is the only line the app ever adds to your own files.

## Files it writes

- `~/.config/hyde-settings/settings.json` (and `.bak`)
- `~/.config/hypr/ui.lua` (and `.bak`)
- one `require("ui")` line at the end of `~/.config/hypr/hyprland.lua` (only when you click "Adicionar")
- `~/.config/mimeapps.list`, through `xdg-mime`

## Development

```sh
python3 -m pytest -q
```

The pure logic is unit-tested and the GTK pages are not:

- unit-tested: settings store and validation, Lua generator (including escaping and a `luac` check), `hyprctl` wrapper, keybind origin/conflict logic, the apply transaction and watchdog, MIME helpers;
- not unit-tested: the GTK pages, which are thin views over that logic.

The design doc is in [`docs/design.md`](docs/design.md).

## License

[MIT](LICENSE)
