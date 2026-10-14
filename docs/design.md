# hyde-settings — Design Spec

**Status:** Draft, awaiting user review
**Author:** Claude (session 23925850), with gladiusdei
**Date:** 2026-10-09
**Target system:** Arch Linux, HyDE (repo `~/HyDE` at fa2fd57a), Hyprland 0.56.2 with the Lua config, libadwaita 1.10, Lua 5.5 (`luac` available)

## 1. Purpose

The user wants a desktop app to change their personal Hyprland/HyDE settings without hand-editing Lua: keybinds, default apps, monitor and input, window rules, and general appearance.

Two constraints come from recent history:

- **Survive HyDE updates.** The 2026-10-06 HyDE update migrated hyprlang `.conf` files to Lua and silently dropped the user's monitor scale, keyboard layout, keybinds and waybar modules. The app must write only to files HyDE never overwrites.
- **Coexist with manual editing.** The user also wants to keep editing Lua by hand. The app must not parse or rewrite hand-written Lua.

**Success:** changing a keybind, an opacity or the default editor takes a few clicks and shows the effect immediately. A bad monitor or keyboard change reverts by itself, and nothing is lost in a HyDE update.

## 2. Decisions made during brainstorming

| Topic | Decision |
|---|---|
| Where it lives | A separate app, `hyde-settings` (not tabs in vaio-center) |
| Manual vs UI | The UI owns its own data file and generates one Lua file, loaded last. Manual `.lua` files stay untouched. |
| v1 scope | Keybinds, default apps, monitor and input, window rules, appearance |
| Existing settings | Migrated once by hand (by Claude) into the app's data file during implementation. No Lua importer. |
| Apply model | An "Apply" button with rollback on error. Dangerous changes (scale, resolution, keyboard layout) need confirmation within 15 s or they revert. |
| Stack | Python 3 + GTK4/libadwaita (same stack as `~/vaio-center`) |

## 3. Background: how the Hyprland config loads today

`HYPRLAND_CONFIG` points to `~/.local/share/hypr/hyde.lua`, which HyDE overwrites on every update. That file runs, in order: `variables`, `defaults`, `window_rules`, `layer_rules`, `env`, `key_binds` (with `hyde.binds.dedup = true`), `dynamic`, `events`, `start_up`, then `check_require("monitors")` and `check_require("hyprland")`.

`package.path` includes `~/.config/hypr/?.lua`, so the user's `~/.config/hypr/hyprland.lua` loads last and can `require` sibling files.

The user's files today:

- `~/.config/hypr/hyprland.lua`: the monitor (eDP-1 1920x1080@144, scale 1) and input settings (kb_layout br, sensitivity 0.7, numlock, natural_scroll), then `require("legacy")` and `require("keybinds")`.
- `~/.config/hypr/legacy.lua`: the window and layer rules ported from the old `windowrules.conf` (44 opacity rules, a float list, idle-inhibit, a JetBrains rule, layer blur).
- `~/.config/hypr/keybinds.lua`: six binds. SUPER+C runs `code`, SUPER+M maximizes, SHIFT+F11 toggles plain fullscreen, ALT+TAB runs `cycle_next`, SUPER+Delete runs `hyde-shell logout`, and ALT+Control_R toggles waybar.

The Hyprland Lua API features this design relies on were confirmed live on 2026-10-09: `hl.bind`, `hl.unbind`, `hl.dsp.submap`, `hl.window_rule`, `hl.layer_rule`, `hl.monitor` and `hl.config`.

## 4. Architecture

```
settings.json ──► generator ──► ~/.config/hypr/ui.lua ──► hyprctl reload
 (single source)                (generated, "do not edit")     │
      ▲                                                        ▼
   UI (GTK) ◄──────── live state (hyprctl -j) ◄──────── Hyprland
```

- **Repository:** `~/hyde-settings`, as a git repo. The package is `hyde_settings/` and the entry point is `hyde-settings`.
- **Hook into Hyprland:** a single `require("ui")` line at the end of `~/.config/hypr/hyprland.lua`, after the manual settings. The generated file therefore overrides HyDE and the manual files.
- **Installation:** `install.sh`, at user level with no root. It copies the app into `~/.local/lib/hyde-settings`, adds a launcher at `~/.local/bin/hyde-settings`, a `.desktop` entry and an optional waybar module in `~/.config/waybar/layouts/hyprdots/gladius.jsonc`. It follows vaio-center's `install.sh` pattern.

### 4.1 Units

Each unit has one purpose and can be tested on its own.

| Unit | Responsibility | Depends on |
|---|---|---|
| `store.py` | Load and save `~/.config/hyde-settings/settings.json`. Atomic write (tmp + rename), schema validation, version check. | none |
| `generator.py` | Pure function from settings to Lua source text. Deterministic output order and string escaping. | none |
| `hypr.py` | Thin wrapper over `hyprctl`: `binds -j`, `getoption -j`, `monitors -j`, `devices -j`, `clients -j`, `configerrors`, `reload`, submap enter and exit. Commands run through an injectable runner so tests can fake them. | `hyprctl` |
| `mime.py` | Read and write default apps in `~/.config/mimeapps.list` through `xdg-mime`. List installed `.desktop` apps and the MIME types they handle. | `xdg-mime`, `.desktop` files |
| `apply.py` | The apply transaction (section 6), plus the revert watchdog entry point `--revert-after`. | store, generator, hypr |
| `binds.py` | Pure logic for keybinds: merge the live binds with the settings, tag each bind's origin, group binds by category, detect conflicts, normalize key combos. | none |
| `pages/*.py` | One GTK page per section: `keybinds`, `apps`, `display` (monitor and input), `rules`, `appearance`. | the units above |
| `app.py` | The `Adw.Application` and the main window (`AdwNavigationSplitView`, the Apply/Discard bar, global search). | pages |

## 5. Data model

The file is `~/.config/hyde-settings/settings.json`. A `null` value means "not overridden, HyDE's value applies".

```json
{
  "version": 1,
  "monitors": [
    {"output": "eDP-1", "mode": "1920x1080@144", "position": "auto", "scale": 1.0}
  ],
  "input": {
    "kb_layout": "br", "kb_variant": null, "sensitivity": 0.7,
    "numlock_by_default": true, "natural_scroll": true
  },
  "appearance": {
    "active_opacity": null, "inactive_opacity": null,
    "gaps_in": null, "gaps_out": null, "border_size": null,
    "rounding": null,
    "blur": {"enabled": null, "size": null, "passes": null}
  },
  "apps": {
    "editor":   {"command": "code", "key": "SUPER + C"},
    "browser":  {"command": null,   "key": "SUPER + B"},
    "terminal": {"command": null,   "key": "SUPER + T"},
    "explorer": {"command": null,   "key": "SUPER + E"}
  },
  "binds": [
    {"key": "SUPER + M", "action": {"type": "dispatch", "name": "maximize"},
     "description": "[Window Management] toggle maximize"},
    {"key": "SUPER + Delete", "action": {"type": "exec", "command": "hyde-shell logout"},
     "description": "[Window Management] kill hyprland session"},
    {"key": "SUPER + G", "action": {"type": "unbind"}}
  ],
  "window_rules": [
    {"name": "kitty", "match": {"class": "^(kitty)$"},
     "opacity": [0.90, 0.80, 1.0], "float": null, "idle_inhibit": null}
  ],
  "layer_rules": [
    {"name": "blur-overlays",
     "match": {"namespace": "^(rofi|notifications|swaync-notification-window|swaync-control-center|logout_dialog)$"},
     "blur": true, "ignore_alpha": 0}
  ]
}
```

### 5.1 Field rules

- **`version`** must be `1`. An unknown version or invalid JSON puts the app in read-only mode (section 7).
- **`monitors[].mode`** is one of the modes `hyprctl monitors -j` reports for that output, or `"preferred"`. **`scale`** is a positive float. **`position`** is `"auto"` or `"XxY"`.
- **`binds[].key`** is a normalized combo: modifiers in a fixed order (SUPER, CTRL, ALT, SHIFT), then the key. **`action.type`** is one of:
  - `exec`, with a `command` string;
  - `dispatch`, with a `name` from the curated list (5.2) and optional `args`;
  - `unbind`, which removes HyDE's or a manual bind without replacing it.
- **`apps.<role>.command`**: `null` keeps HyDE's launcher bind. A string replaces the bind on `apps.<role>.key`.
- **`window_rules[].match`** takes `class`, `title` or `initial_title` regexes. **`opacity`** is `[active, inactive]` or `[active, inactive, fullscreen]`. Values are absolute: the generator emits `override` after each, so they are not multiplied by the global active/inactive opacity. **`float`** is a bool or null. **`idle_inhibit`** is `"always"`, `"fullscreen"` or null. For `"fullscreen"`, the generator adds `fullscreen = true` to the match and emits `idle_inhibit = "always"`.
- **`layer_rules`** exists so the layer blur from `legacy.lua` can be migrated too. In v1 the UI shows layer rules read-only.

### 5.2 Curated dispatchers (v1)

| `name` | Generated Lua |
|---|---|
| `close` | `hl.dsp.window.close()` |
| `kill` | `hl.dsp.window.kill()` |
| `maximize` | `hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })` |
| `fullscreen` | `hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" })` |
| `float` | `hl.dsp.window.float({ action = "toggle" })` |
| `cycle_next` | `hl.dsp.window.cycle_next()` |
| `workspace` (args: n) | `hl.dsp.focus({ workspace = n })` |
| `move_to_workspace` (args: n) | `hl.dsp.window.move({ workspace = n })` |

`ALT + Control_R` (toggle waybar) migrates as `exec` with `hyde-shell waybar --hide`.

## 6. Generated Lua and the apply transaction

### 6.1 Generator output

`~/.config/hypr/ui.lua` has a fixed section order: header, capture submap, monitors, `hl.config` for input and appearance, app binds, binds, window rules, layer rules.

```lua
-- GENERATED BY hyde-settings — do not edit; change it in the app.
-- Source: ~/.config/hyde-settings/settings.json

-- Escape hatch for keybind capture: Escape always leaves the capture submap.
hl.bind("Escape", hl.dsp.submap("reset"), { submap = "hs_capture" })

hl.monitor({ output = "eDP-1", mode = "1920x1080@144", position = "auto", scale = 1.0 })
hl.config({ input = { kb_layout = "br", sensitivity = 0.7, numlock_by_default = true,
  touchpad = { natural_scroll = true } } })

hl.unbind("SUPER + C")
hl.bind("SUPER + C", hl.dsp.exec_cmd("code"), { description = "[Launcher|Apps] text editor" })

hl.window_rule({ name = "hs-kitty", match = { class = "^(kitty)$" }, opacity = "0.90 0.80 1.0" })
```

Generator rules:

- **Binds:** every bind in the UI emits `hl.unbind(key)` before `hl.bind(...)`. A replaced bind then never duplicates HyDE's, whatever flags HyDE used.
- **Escaping:** every string is emitted as a Lua quoted string with `\\`, `"`, newlines and control characters escaped. User input never ends up inside long brackets or raw code.
- **Nulls:** `null` fields produce no Lua at all. An all-null section produces no call.
- **Rule names:** window rule names get an `hs-` prefix, which avoids clashes with HyDE's rule names.
- **Determinism:** the same settings always produce byte-identical output.

The submap API (`hl.dsp.submap`, and the `submap` option on `hl.bind`) is confirmed to exist. The exact option name for binding inside a submap gets verified in the first implementation task. If it differs, only the escape-hatch line changes.

### 6.2 Apply transaction (`apply.py`)

1. Validate the pending settings against the schema.
2. Generate the Lua and check it with `luac -p` on a temp file. On failure, stop and show the error. Nothing is written.
3. Copy `ui.lua` to `ui.lua.bak` (if it exists), then write the new `ui.lua` atomically.
4. Run `hyprctl reload`, then `hyprctl configerrors`.
5. **On errors:** restore `ui.lua.bak`, reload again and show the exact error text. `settings.json` is not saved, so the changes stay pending.
6. **On success:** save `settings.json` atomically and clear the pending state.

### 6.3 Confirmation for dangerous changes

Dangerous means a change to `monitors` or `input.kb_layout` / `input.kb_variant`.

- Before step 4, apply starts a detached watchdog with `systemd-run --user --unit=hyde-settings-revert --collect hyde-settings --revert-after 15 <backup-path>`.
- The watchdog sleeps 15 s, then restores the backup and runs `hyprctl reload`, unless it was stopped first.
- The UI shows "Keep these settings? Reverting in 15 s…" with **Keep** and **Revert**. Keep runs `systemctl --user stop hyde-settings-revert`, then saves `settings.json`. Revert, a timeout, or the app dying all leave the watchdog to restore the backup. `settings.json` stays unsaved.
- The timer lives outside the UI on purpose: an unreadable screen or a crashed app still reverts.

### 6.4 Keybind capture

- Opening the capture dialog runs `hyprctl dispatch submap hs_capture`. The submap holds only the Escape bind, so Hyprland executes no other bind and GTK receives the combo through `Gtk.EventControllerKey`.
- The dialog leaves the submap (`submap reset`) on capture, on cancel, after 10 s, and on window close.
- If the app crashes mid-capture, pressing Escape restores normal binds.

## 7. Error handling

| Situation | Behaviour |
|---|---|
| `hyprctl` missing or Hyprland not running | Read-only mode with a banner. Pages show data from `settings.json` only. |
| `settings.json` invalid or of an unknown version | Read-only mode. The banner names the file and suggests restoring from `settings.json.bak` (written on every save). |
| `require("ui")` missing from `hyprland.lua` | A banner with an "Add" button. It appends one line (`require("ui")`) to the end of `~/.config/hypr/hyprland.lua` and never rewrites the file. This is the only write outside the app's own files and `mimeapps.list`. |
| Lua syntax error in the generated file | Caught by `luac -p` before anything is written (6.2 step 2). |
| `hyprctl configerrors` reports errors after reload | Rollback (6.2 step 5). |
| App or bind command not found in PATH | A yellow warning on the row. Saving is still allowed. |
| `xdg-mime` fails | An error toast. Other pending changes are unaffected, because MIME defaults are not part of the Lua transaction. |

## 8. Pages

The main window is an `AdwNavigationSplitView` with the section list on the left. The header bar has global search, **Apply (n)** showing the number of pending changes, and **Discard**.

### 8.1 Keybinds

- Lists all live binds from `hyprctl binds -j`, grouped by the bracketed category in their description, with a search filter.
- Each row shows its origin:
  - **HyDE**: from `~/.local/share/hypr/lua/key_binds.lua`. Editing it creates a UI override.
  - **yours**: from settings. Editable, with reset.
  - **manual**: from a hand-written file under `~/.config/hypr` other than `ui.lua`. Read-only, with a hint naming the file.
- Origin comes from matching each live bind against the settings and against key combos found by a plain-text scan of HyDE's and the manual files. The scan only reads, it does not parse Lua.
- Unbound HyDE binds (`action.type = unbind`) show as "(removed)", with reset.
- The new/edit dialog has the capture field (6.4) and an action picker: "Run command" or a curated dispatcher with its args. A conflict warning appears when the combo is already in use: "SUPER+X already does Y — replace?".

### 8.2 Default apps

- Editor, browser, terminal and file manager. Each has a combo of installed apps from `.desktop` files, plus a free command field. They write `apps.<role>`.
- **Open files with:** text (`text/plain`), code (`text/x-csrc`, `text/x-python`, `text/x-shellscript`, `application/json`, `text/markdown`), PDF, image, video and folder. Each row shows the current default and a combo to change it, written through `xdg-mime default`. These are applied immediately, outside the Lua transaction, with an undo toast.

### 8.3 Monitor and input

- Per monitor: a mode combo from `hyprctl monitors -j` `availableModes`, scale presets (1.0, 1.25, 1.5, 2.0) or a custom value, and position. These changes are dangerous (6.3).
- Keyboard: layout and variant (dangerous). Pointer: sensitivity, natural scroll, numlock.

### 8.4 Window rules

- A list of rules. Each row shows the match and its effects, with an editor for match, opacity, float and idle-inhibit.
- **Pick window** lists open windows from `hyprctl clients -j`, so a class can be filled in without writing a regex. It fills `^(<class>)$` with the class regex-escaped.

### 8.5 Appearance

- Sliders and switches for active/inactive opacity, gaps in/out, border size, rounding and blur (enabled, size, passes).
- Each control shows HyDE's current value, read live with `hyprctl getoption`, and has a reset button that sets the field back to `null`.

## 9. Migration of current settings (one-time, by Claude)

This is a task in the implementation plan, not an app feature.

1. Write `settings.json` with:
   - the monitor and input values from `hyprland.lua`;
   - the six binds from `keybinds.lua`, with SUPER+C going into `apps.editor` (`code`) instead of `binds`;
   - the 44 opacity rules, float list, idle-inhibit rules and JetBrains rule from `legacy.lua` as `window_rules`;
   - the layer blur from `legacy.lua` as `layer_rules`.
2. Generate `ui.lua` and diff the live state (`hyprctl binds -j`, `getoption`, `monitors -j`) before and after. It must be identical apart from rule names.
3. Reduce `legacy.lua` and `keybinds.lua` to comment-only templates for manual use. Remove the monitor and input blocks from `hyprland.lua`, and add `require("ui")` at the end.
4. Keep a backup of the three files at `~/.config/hypr/pre-hyde-settings/` until the user confirms.

## 10. Testing

- **pytest with TDD**, as in vaio-center.
- **`generator`:**
  - golden-text tests per section;
  - escaping tests (quotes, backslash, newline, `]]`);
  - `luac -p` on every generated output in the test suite;
  - a determinism test.
- **`store`:** round trip, atomic write (no partial file on a simulated crash), invalid JSON, unknown version, `.bak` on save.
- **`binds`:** combo normalization, origin tagging, category grouping and conflict detection. Fixtures are `hyprctl binds -j` output captured from this machine.
- **`apply`:** a fake `hyprctl` runner, covering:
  - success;
  - a configerrors rollback;
  - a `luac` failure that writes nothing;
  - dangerous changes that start the watchdog;
  - Keep stopping the watchdog;
  - the `--revert-after` entry point restoring the backup.
- **`hypr` and `mime`:** parsing against captured JSON and a sample `mimeapps.list`.
- **GTK pages:** only their pure logic is unit-tested. A manual checklist at the end covers:
  - each page loads;
  - capture with SUPER combos;
  - a dangerous change reverting after 15 s without confirmation;
  - a broken rule rolling back.

## 11. Out of scope for v1

- startup apps;
- theme, wallpaper, animation and waybar layout (HyDE already has pickers for these);
- binds with free-form Lua;
- editing layer rules in the UI;
- multiple profiles;
- sync between machines;
- non-Hyprland compositors.
