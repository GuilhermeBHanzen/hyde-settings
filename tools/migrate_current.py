"""One-time migration (2026-10): the settings that lived in hyprland.lua, legacy.lua and keybinds.lua."""
import sys

from hyde_settings import apply, generator, rules, store

OPACITY = (  # (match, [active, inactive(, fullscreen)]) from legacy.lua
    ({"class": "^(firefox)$"}, [1.0, 0.9, 1.0]),
    ({"class": "^(brave-browser)$"}, [1.0, 0.9, 1.0]),
    ({"class": "^([Cc]ode)$"}, [1.0, 0.8, 1.0]),
    ({"class": "^(code-url-handler)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(code-insiders-url-handler)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(kitty)$"}, [0.9, 0.8, 1.0]),
    ({"class": "^(org.kde.dolphin)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(org.kde.ark)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(nwg-look)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(qt5ct)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(qt6ct)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(kvantummanager)$"}, [0.8, 0.8, 1.0]),
    ({"class": "^(org.pulseaudio.pavucontrol)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(blueman-manager)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(nm-applet)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(nm-connection-editor)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(org.kde.polkit-kde-authentication-agent-1)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(polkit-gnome-authentication-agent-1)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(org.freedesktop.impl.portal.desktop.gtk)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^(org.freedesktop.impl.portal.desktop.hyprland)$"}, [0.8, 0.7, 1.0]),
    ({"class": "^([Ss]team)$"}, [0.7, 0.7, 1.0]),
    ({"class": "^(steamwebhelper)$"}, [0.7, 0.7, 1.0]),
    ({"class": "^([Ss]potify)$"}, [0.7, 0.7, 1.0]),
    ({"initial_title": "^(Spotify Free)$"}, [0.7, 0.7, 1.0]),
    ({"initial_title": "^(Spotify Premium)$"}, [0.7, 0.7, 1.0]),
    ({"class": "^(com.github.rafostar.Clapper)$"}, [0.9, 0.9]),
    ({"class": "^(com.github.tchx84.Flatseal)$"}, [0.8, 0.8]),
    ({"class": "^(hu.kramo.Cartridges)$"}, [0.8, 0.8]),
    ({"class": "^(com.obsproject.Studio)$"}, [0.8, 0.8]),
    ({"class": "^(gnome-boxes)$"}, [0.8, 0.8]),
    ({"class": "^(vesktop)$"}, [0.8, 0.8]),
    ({"class": "^(discord)$"}, [0.8, 0.8]),
    ({"class": "^(WebCord)$"}, [0.8, 0.8]),
    ({"class": "^(ArmCord)$"}, [0.8, 0.8]),
    ({"class": "^(app.drey.Warp)$"}, [0.8, 0.8]),
    ({"class": "^(net.davidotek.pupgui2)$"}, [0.8, 0.8]),
    ({"class": "^(yad)$"}, [0.8, 0.8]),
    ({"class": "^(Signal)$"}, [0.8, 0.8]),
    ({"class": "^(io.github.alainm23.planify)$"}, [0.8, 0.8]),
    ({"class": "^(io.gitlab.theevilskeleton.Upscaler)$"}, [0.8, 0.8]),
    ({"class": "^(com.github.unrud.VideoDownloader)$"}, [0.8, 0.8]),
    ({"class": "^(io.gitlab.adhami3310.Impression)$"}, [0.8, 0.8]),
    ({"class": "^(io.missioncenter.MissionCenter)$"}, [0.8, 0.8]),
    ({"class": "^(io.github.flattool.Warehouse)$"}, [0.8, 0.8]),
)
FLOAT_CLASSES = (
    "^(Signal)$|^(com.github.rafostar.Clapper)$|^(app.drey.Warp)$|^(net.davidotek.pupgui2)$"
    "|^(yad)$|^(eog)$|^(io.github.alainm23.planify)$|^(io.gitlab.theevilskeleton.Upscaler)$"
    "|^(com.github.unrud.VideoDownloader)$|^(io.gitlab.adhami3310.Impression)$"
    "|^(io.missioncenter.MissionCenter)$"
)
IDLE = (
    ("idle-video-players", "^(.*celluloid.*)$|^(.*mpv.*)$|^(.*vlc.*)$"),
    ("idle-spotify", "^(.*[Ss]potify.*)$"),
    ("idle-browsers", "^(.*LibreWolf.*)$|^(.*floorp.*)$|^(.*brave-browser.*)$|^(.*firefox.*)$"
                      "|^(.*chromium.*)$|^(.*zen.*)$|^(.*vivaldi.*)$"),
)


def build():
    s = store.default_settings()
    s["monitors"] = [{"output": "eDP-1", "mode": "1920x1080@144", "position": "auto", "scale": 1.0}]
    s["input"].update(kb_layout="br", sensitivity=0.7, numlock_by_default=True, natural_scroll=True)
    s["apps"]["editor"]["command"] = "code"
    s["binds"] = [
        {"key": "SUPER + M", "action": {"type": "dispatch", "name": "maximize"},
         "description": "[Window Management] toggle maximize"},
        {"key": "SHIFT + F11", "action": {"type": "dispatch", "name": "fullscreen"},
         "description": "[Window Management] toggle fullscreen"},
        {"key": "ALT + TAB", "action": {"type": "dispatch", "name": "cycle_next"},
         "description": "[Window Management|Change focus] cycle focus"},
        {"key": "SUPER + Delete", "action": {"type": "exec", "command": "hyde-shell logout"},
         "description": "[Window Management] kill hyprland session"},
        {"key": "ALT + Control_R", "action": {"type": "exec", "command": "hyde-shell waybar --hide"},
         "description": "[Window Management] toggle waybar and reload config"},
    ]
    taken = set()
    for match, opacity in OPACITY:
        name = rules.unique_name(next(iter(match.values())), taken)
        taken.add(name)
        s["window_rules"].append({"name": name, "match": match, "opacity": opacity,
                                  "float": None, "idle_inhibit": None})
    s["window_rules"].append({"name": "float-legacy", "match": {"class": FLOAT_CLASSES},
                              "opacity": None, "float": True, "idle_inhibit": None})
    for name, pattern in IDLE:
        s["window_rules"].append({"name": name, "match": {"class": pattern},
                                  "opacity": None, "float": None, "idle_inhibit": "fullscreen"})
    s["layer_rules"] = [{
        "name": "blur-overlays",
        "match": {"namespace": "^(rofi|notifications|swaync-notification-window|swaync-control-center|logout_dialog)$"},
        "blur": True, "ignore_alpha": 0,
    }]
    return s


def main():
    settings = build()
    text = generator.generate(settings)
    err = apply.check_syntax(text)
    if err:
        print(f"migrate: generated Lua is invalid: {err}", file=sys.stderr)
        return 1
    store.save(settings)
    store.write_atomic(apply.ui_lua_path(), text)
    print(f"migrate: wrote {store.settings_path()} and {apply.ui_lua_path()} "
          f"({len(settings['window_rules'])} window rules, {len(settings['binds'])} binds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
